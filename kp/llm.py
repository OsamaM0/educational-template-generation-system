"""Three interchangeable LLMs behind one method: complete(step, messages, schema, meta) -> dict.

OpenRouterLLM
            the real one. It uses the official OpenAI client against
            OpenRouter's OpenAI-compatible base URL. Structured outputs
            (`response_format=<pydantic model>`) are parsed and schema-valid or
            the call fails loudly. Models are OpenRouter ids, e.g.
            LLM_MODEL_MATH=openai/gpt-4o and
            LLM_MODEL_NORMAL=openai/gpt-4o-mini.
ReplayLLM   replays an authored record (demo + tests). Can inject faults to
            exercise the repair loop.
StubLLM     deterministic placeholder text for ANY lesson — for smoke-testing
            the pipeline on real data without spending tokens. Its output is
            marked «[نص تجريبي]» and must never be published.

`meta` carries the structured inputs (goals, topic, questions…) so the two
stand-ins can answer without parsing prompts.
"""
import copy
import json
import re
from dataclasses import dataclass, field


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    by_step: dict = field(default_factory=dict)
    by_model: dict = field(default_factory=dict)
    models: dict = field(default_factory=dict)

    def add(self, step, model, u):
        inp = getattr(u, "prompt_tokens", 0) or 0
        out = getattr(u, "completion_tokens", 0) or 0
        det = getattr(u, "prompt_tokens_details", None)
        cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
        self.calls += 1; self.input_tokens += inp; self.output_tokens += out; self.cached_tokens += cached
        b = self.by_step.setdefault(step, {"calls": 0, "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0})
        b["calls"] += 1; b["input_tokens"] += inp; b["cached_tokens"] += cached; b["output_tokens"] += out
        m = self.by_model.setdefault(model, {"calls": 0, "input_tokens": 0,
                                             "cached_tokens": 0, "output_tokens": 0})
        m["calls"] += 1; m["input_tokens"] += inp; m["cached_tokens"] += cached; m["output_tokens"] += out
        self.models[step] = model

    def merge(self, other):
        for step, b in other.by_step.items():
            mine = self.by_step.setdefault(step, {k: 0 for k in b})
            for k, v in b.items():
                mine[k] += v
        for model, b in other.by_model.items():
            mine = self.by_model.setdefault(model, {k: 0 for k in b})
            for k, v in b.items():
                mine[k] += v
        self.calls += other.calls; self.input_tokens += other.input_tokens
        self.cached_tokens += other.cached_tokens; self.output_tokens += other.output_tokens
        self.models.update(other.models)

    def cost(self, s):
        return round(sum(
            ((b["input_tokens"] - b["cached_tokens"]) * s.prices_for_model(model)[0]
             + b["cached_tokens"] * s.prices_for_model(model)[1]
             + b["output_tokens"] * s.prices_for_model(model)[2]) / 1e6
            for model, b in self.by_model.items()), 6)

    def as_dict(self, s=None):
        d = {"calls": self.calls, "input_tokens": self.input_tokens, "cached_tokens": self.cached_tokens,
             "output_tokens": self.output_tokens, "total_tokens": self.input_tokens + self.output_tokens,
             "by_step": self.by_step, "by_model": self.by_model, "models": self.models}
        if s is not None:
            d["estimated_cost_usd"] = self.cost(s)
            d["cost_by_model_usd"] = {
                model: round(((b["input_tokens"] - b["cached_tokens"]) * s.prices_for_model(model)[0]
                              + b["cached_tokens"] * s.prices_for_model(model)[1]
                              + b["output_tokens"] * s.prices_for_model(model)[2]) / 1e6, 6)
                for model, b in self.by_model.items()}
        return d


def is_reasoning(model):
    m = (model or "").lower()
    # Strip an OpenRouter vendor prefix (openai/gpt-5, openai/o3, …) before testing.
    m = m.split("/")[-1]
    return m.startswith(("gpt-5", "o1", "o3", "o4"))


def is_openrouter(settings):
    base = (getattr(settings, "llm_base_url", "") or "").lower()
    return "openrouter" in base


# ========================================== OpenRouter (OpenAI-compatible API)
class OpenRouterLLM:
    name = "openrouter"

    def __init__(self, settings, client=None):
        from openai import OpenAI
        if client is None and not settings.llm_api_key:
            raise LLMError("OPENROUTER_API_KEY is not set.")
        self.s = settings
        if client is not None:
            self.client = client
        else:
            kwargs = {"api_key": settings.llm_api_key, "timeout": settings.request_timeout, "max_retries": 0}
            base = (getattr(settings, "llm_base_url", "") or "").strip()
            if base:
                kwargs["base_url"] = base
            headers = {}
            referer = (getattr(settings, "llm_referer", "") or "").strip()
            title = (getattr(settings, "llm_title", "") or "").strip()
            if referer:
                headers["HTTP-Referer"] = referer
            if title:
                headers["X-Title"] = title
            if headers:
                kwargs["default_headers"] = headers
            self.client = OpenAI(**kwargs)
        # When a test injects a mock client, the client's own base_url wins over
        # the ambient .env — otherwise a local OpenRouter base URL would
        # flip unit-test expectations that use the default OpenAI endpoint.
        try:
            client_base = str(getattr(self.client, "base_url", "") or "")
        except Exception:
            client_base = ""
        if client is not None:
            self._openrouter = "openrouter" in client_base.lower()
        else:
            self._openrouter = is_openrouter(settings)
        self.usage = Usage()
        self._token_caps = {}

    def model_for(self, step):
        return self.s.model_link if step == "link" else self.s.model_creative

    def _kwargs_for(self, model, step=None):
        # OpenRouter's OpenAI-compatible endpoint accepts temperature broadly,
        # while reasoning_effort is an OpenAI-only parameter that some
        # providers reject. On OpenRouter always use temperature.
        if self._openrouter:
            kwargs = {"temperature": self.s.temperature}
            effort = (self.s.link_reasoning_effort if step == 'link'
                      else self.s.creative_reasoning_effort)
            if effort != 'provider':
                kwargs['extra_body'] = {'reasoning': {'effort': effort}}
        else:
            effort = (self.s.link_reasoning_effort if step == 'link' and self.s.link_reasoning_effort != 'provider'
                      else self.s.reasoning_effort)
            kwargs = {"reasoning_effort": effort} if is_reasoning(model) else {"temperature": self.s.temperature}
        max_tok = int(getattr(self.s, "max_tokens", 0) or 0)
        if max_tok > 0:
            max_tok = max(max_tok, min(self._token_caps.get(model, 0), self.s.max_retry_tokens))
            # Reasoning models use max_completion_tokens; others use max_tokens.
            if not self._openrouter and is_reasoning(model):
                kwargs["max_completion_tokens"] = max_tok
            else:
                kwargs["max_tokens"] = max_tok
        return kwargs

    def _parse_response(self, resp, step, model):
        # A provider can bill a response even when its structured body is unusable.
        self.usage.add(step, model, getattr(resp, "usage", None))
        choice = resp.choices[0]
        if getattr(choice.message, "refusal", None):
            raise LLMError(f"{step}: the model refused: {choice.message.refusal}")
        parsed = getattr(choice.message, "parsed", None)
        if parsed is not None:
            return parsed.model_dump()
        # Fallback for providers that return JSON text without the SDK's
        # parsed helper (OpenRouter on some models): parse content manually.
        content = getattr(choice.message, "content", None)
        if content:
            try:
                from pydantic import TypeAdapter
                data = json.loads(content) if isinstance(content, str) else content
                adapter = TypeAdapter(self._last_schema) if hasattr(self, "_last_schema") else None
                if adapter is not None:
                    validated = adapter.validate_python(data)
                    return validated.model_dump() if hasattr(validated, "model_dump") else dict(validated)
            except Exception:
                pass
        raise LLMError(f"{step}: no parsed output")

    def complete(self, step, messages, schema, meta=None):
        import openai
        from pydantic import TypeAdapter, ValidationError
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

        model = self.model_for(step)
        self._last_schema = schema
        kwargs = self._kwargs_for(model, step)
        completions = self.client.chat.completions
        parse = getattr(completions, "parse", None) or self.client.beta.chat.completions.parse
        transient = (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError)

        def retry_progress(state):
            report = (meta or {}).get('_progress')
            if report:
                report(step, goal_id=(meta or {}).get('goal_id'), state='retry',
                       attempt=state.attempt_number,
                       error=type(state.outcome.exception()).__name__,
                       wait_seconds=state.next_action.sleep)

        @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60),
               retry=retry_if_exception_type(transient), reraise=True, before_sleep=retry_progress)
        def call():
            try:
                return parse(model=model, messages=messages, response_format=schema, **kwargs)
            except openai.LengthFinishReasonError as exc:
                self.usage.add(step, model, getattr(getattr(exc, 'completion', None), 'usage', None))
                token_key = 'max_completion_tokens' if 'max_completion_tokens' in kwargs else 'max_tokens'
                cap = kwargs.get(token_key, 0)
                ceiling = self.s.max_retry_tokens
                if not cap or cap >= ceiling:
                    raise
                kwargs[token_key] = min(cap * 2, ceiling)
                report = (meta or {}).get('_progress')
                if report:
                    report(step, goal_id=(meta or {}).get('goal_id'), state='retry',
                           reason='token_limit', max_tokens=kwargs[token_key])
                try:
                    return parse(model=model, messages=messages, response_format=schema, **kwargs)
                except openai.LengthFinishReasonError as retry_exc:
                    self.usage.add(step, model, getattr(getattr(retry_exc, 'completion', None), 'usage', None))
                    raise

        try:
            resp = call()
        except transient as e:
            raise LLMError(f"{step}: provider unavailable after retries ({type(e).__name__})") from e
        except openai.LengthFinishReasonError as e:
            raise LLMError(f"{step}: the reply hit the token limit before the JSON closed") from e
        except ValidationError as e:
            # Some OpenRouter models wrap otherwise valid structured JSON in a
            # Markdown code fence. The SDK raises before exposing a response.
            def recover(error):
                raw = next((item.get('input') for item in error.errors()
                            if isinstance(item.get('input'), str)), None)
                if not raw:
                    return None
                candidate = raw.strip()
                if candidate.startswith('```') and candidate.endswith('```'):
                    candidate = re.sub(r'^```(?:json)?\s*', '', candidate, flags=re.IGNORECASE)
                    candidate = re.sub(r'\s*```$', '', candidate)
                try:
                    parsed_json = json.loads(candidate)
                except ValueError:
                    # A provider may prepend a short explanation to an otherwise
                    # valid JSON object. Accept only an object matching the schema.
                    parsed_json = None
                    decoder = json.JSONDecoder()
                    for match in re.finditer(r'\{', candidate):
                        try:
                            parsed_json, _ = decoder.raw_decode(candidate[match.start():])
                            break
                        except ValueError:
                            continue
                if parsed_json is None:
                    return None
                try:
                    parsed = TypeAdapter(schema).validate_python(parsed_json)
                    return parsed.model_dump() if hasattr(parsed, 'model_dump') else dict(parsed)
                except (TypeError, ValidationError):
                    return None

            recovered = recover(e)
            if recovered is not None:
                self.usage.add(step, model, None)
                return recovered
            report = (meta or {}).get('_progress')
            if report:
                report(step, goal_id=(meta or {}).get('goal_id'), state='retry',
                       reason='invalid_json', attempt=2)
            try:
                repaired = parse(model=model, messages=messages + [{
                    'role': 'user', 'content': 'Return the requested data again as valid JSON matching the response schema. No code fence or prose.'
                }], response_format=schema, **kwargs)
                result = self._parse_response(repaired, step, model)
                cap = kwargs.get('max_completion_tokens', kwargs.get('max_tokens', 0))
                if cap:
                    self._token_caps[model] = cap
                return result
            except ValidationError as retry_error:
                recovered = recover(retry_error)
                if recovered is not None:
                    self.usage.add(step, model, None)
                    return recovered
                raise LLMError(f'{step}: provider returned invalid structured JSON ({retry_error.errors()[0]["type"]})') from retry_error
            except openai.APIError as retry_error:
                raise LLMError(f'{step}: JSON retry failed ({type(retry_error).__name__})') from retry_error
        except openai.BadRequestError as e:
            msg = str(e).lower()
            # Retry once without the sampling param when the provider rejects it
            # (e.g. reasoning_effort on OpenRouter, or temperature on o-series).
            if ("reasoning" in msg or "temperature" in msg or "unsupported" in msg) and kwargs:
                try:
                    fallback = {k: v for k, v in kwargs.items()
                                if k not in {'temperature', 'reasoning_effort', 'extra_body'}}
                    resp = parse(model=model, messages=messages, response_format=schema, **fallback)
                    return self._parse_response(resp, step, model)
                except Exception:
                    pass
            # Fallback: plain create with json_schema, for providers whose
            # parse helper is stricter than their create endpoint.
            if "response_format" in msg or "strict" in msg or "json_schema" in msg:
                try:
                    raw = completions.create(model=model, messages=messages,
                                             response_format={"type": "json_object"},
                                             **({} if kwargs and "temperature" in str(msg) else kwargs))
                    choice = raw.choices[0]
                    content = getattr(choice.message, "content", None)
                    if content:
                        from pydantic import TypeAdapter
                        data = json.loads(content)
                        validated = TypeAdapter(schema).validate_python(data)
                        self.usage.add(step, model, raw.usage)
                        return validated.model_dump()
                except Exception:
                    pass
            provider = "OpenRouter" if self._openrouter else "OpenAI-compatible provider"
            raise LLMError(f"{step}: {provider} rejected the request: {e}") from e
        except openai.APIError as e:
            raise LLMError(f"{step}: provider request failed ({type(e).__name__}): {e}") from e
        result = self._parse_response(resp, step, model)
        cap = kwargs.get('max_completion_tokens', kwargs.get('max_tokens', 0))
        if cap:
            self._token_caps[model] = cap
        return result


# Backward-compatible import for integrations that used the old class name.
OpenAILLM = OpenRouterLLM


# ============================================================== Replay
def replay_answers(record):
    """An authored ai.knowledge_productions record → what each step would have returned."""
    topics, projects, links = [], {}, {}
    for p in record["products"]:
        i, pay, ft = p["idea"], p["payoff"], p["final_task"]
        refs = list(dict.fromkeys([s["question_ref"] for s in p["stages"]] + list(ft.get("question_refs") or [])))
        topics.append({"goal_id": p["goal_id"], "archetype": i["archetype"], "title": i["title"],
                       "subtitle": i["subtitle"], "kind_line": i["kind_line"], "stage_label": i["stage_label"],
                       "premise": i["premise"], "concept_transfer": i["concept_transfer"],
                       "concepts": p.get("concepts", []), "question_refs": refs})
        projects[p["goal_id"]] = {
            "intro": p["intro"],
            "payoff": {"title": pay["title"], "instruction": pay["instruction"],
                       "solution": pay.get("solution"), "meaning": pay.get("meaning"),
                       "columns": pay.get("columns"), "verdict": pay.get("verdict"), "layers": pay.get("layers")},
            "final_task": {"title": ft["title"], "prompt": ft["prompt"], "deliverable": ft["deliverable"], "rubric": ft["rubric"]},
            "reveal": p["reveal"]}
        links[p["goal_id"]] = {"stages": [{
            "question_ref": s["question_ref"], "question_text": s.get("question_text", ""),
            "choices": s.get("choices"), "answer_text": s.get("answer_text"),
            "title": s["title"], "scene": s["scene"], "explanation": s["explanation"],
            "word_bank": s["yields"].get("bank"), "finding": s["yields"].get("finding"),
            "component": s["yields"].get("component"), "layer": s["yields"].get("layer")} for s in p["stages"]],
            "final_questions": copy.deepcopy(ft.get("questions") or [])}
    return topics, projects, links


class ReplayLLM:
    name = "replay"
    legacy_archetypes = True

    def __init__(self, record, faults=None):
        self.legacy_archetypes = not all('sections' in p for p in record['products'])
        if self.legacy_archetypes:
            self.topics, self.projects, self.links = replay_answers(record)
        else:
            from .production_models import ProductionTopic
            fields = set(ProductionTopic.model_fields) - {'question_refs'}
            self.topics = [{**{k:p[k] for k in fields},
                            'question_refs':[q['question_ref'] for q in p['questions']]}
                           for p in record['products']]
            self.projects = {p['goal_id']:{'sections':copy.deepcopy(p['sections'])} for p in record['products']}
            self.links = {p['goal_id']:{'questions':copy.deepcopy(p['questions'])} for p in record['products']}
        self.faults = dict(faults or {})        # {"link:goal_1": 1} → first N link calls for goal_1 are broken
        self.usage = Usage()
        self.log = []

    def complete(self, step, messages, schema, meta=None):
        meta = meta or {}
        gid = meta.get("goal_id")
        self.log.append((step, gid, any("لم تجتز الفحص" in m["content"] for m in messages if m["role"] == "user")))
        if step == "topics":
            wanted = {g["id"] for g in meta["goals"]}
            return {"topics": [copy.deepcopy(t) for t in self.topics if t["goal_id"] in wanted]}
        if step == "project":
            return copy.deepcopy(self.projects[gid])
        out = copy.deepcopy(self.links[gid])
        if not self.legacy_archetypes:
            return out
        if not out.get("final_questions"):
            staged = {s["question_ref"] for s in out["stages"]}
            out["final_questions"] = [{"question_ref": q["id"], "question_text": q["text"],
                                       "choices": q.get("choices") if q["kind"] == "multiple_choice" else None,
                                       "answer_text": q["answer"]}
                                      for q in meta.get("questions", []) if q["id"] not in staged]
        key = f"link:{gid}"
        if self.faults.get(key, 0) > 0:                  # a realistic model mistake
            self.faults[key] -= 1
            out["stages"][1]["question_ref"] = out["stages"][0]["question_ref"]
        return out


# ============================================================== Stub
class StubLLM:
    """Placeholder text for any lesson; exercises storage and rendering, not quality."""
    name = "stub"
    MARK = "[نص تجريبي] "
    MARK_EN = "[Test placeholder] "

    def __init__(self):
        self.usage = Usage()

    def complete(self, step, messages, schema, meta=None):
        meta = meta or {}
        lang = meta.get("language", "ar")
        if meta.get('generalized'):
            from .production_stub import complete
            return complete(step, meta)
        M = self.MARK_EN if lang == "en" else self.MARK
        if step == "topics":
            subject = meta.get("subject") or ("the lesson" if lang == "en" else "الدرس")
            if lang == "en" and any("\u0600" <= ch <= "\u06ff" for ch in subject):
                subject = "the lesson"
            return {"topics": [{
                "goal_id": g["id"], "archetype": "blueprint" if g.get("cognitive_level") in ("apply", "create") else "case_file",
                "title": (f"{M}Project {n}" if lang == "en" else f"{M}الملف {n}"),
                "subtitle": ("From question to outcome" if lang == "en" else "من السؤال إلى الناتج"),
                "kind_line": (f"Applied knowledge production in {subject}" if lang == "en"
                              else f"إنتاج معرفي تطبيقي في {subject}"),
                "stage_label": ("Stage" if lang == "en" else "المحطة"),
                "premise": (f"{M}This temporary idea exercises every stage of the pipeline and is replaced by authored lesson content."
                            if lang == "en" else f"{M}فكرة مؤقتة لهذا الهدف تُستبدل بعد تشغيل النموذج الحقيقي على الدرس نفسه."),
                "concept_transfer": (f"{M}The lesson concepts move into an applied task whose answers combine into one final outcome."
                                     if lang == "en" else f"{M}تنتقل مفاهيم الهدف إلى مهمة تطبيقية تُجمع فيها الإجابات في ناتج واحد."),
                "concepts": ([f"Lesson concept {n}"] if lang == "en" else [g["text"][:40]]),
                "question_refs": [q["id"] for q in g.get("questions", [])[:g.get("max_questions", 8)]]
            } for n, g in enumerate(meta["goals"], 1)]}
        if step == "project":
            arch = meta["topic"]["archetype"]
            layers = (["Layer one: foundation", "Layer two: application"] if lang == "en" else
                      ["الطبقة الأولى: الأساس", "الطبقة الثانية: التطبيق"]) if arch == "blueprint" else None
            objective = "Apply the lesson goal." if lang == "en" else meta["goal_text"]
            return {"intro": {"story": ([f"{M}Temporary story introduction."] if lang == "en" else [f"{M}تمهيد مؤقت للقصة."]),
                              "objective": objective, "rules_title": ("Rules" if lang == "en" else "القواعد"),
                              "rules": (["Read the complete stage.", "Record the outcome of every stage."] if lang == "en"
                                        else ["اقرأ المرحلة كاملة.", "دوّن ناتج كل مرحلة."])},
                    "payoff": {"title": ("Outcome board" if lang == "en" else "لوحة الناتج"),
                               "instruction": (f"{M}Record the outcome after every stage." if lang == "en" else f"{M}دوّن الناتج بعد كل مرحلة."),
                               "solution": None, "meaning": None,
                               "columns": (["Stage", "My decision", "My observation"] if lang == "en" else ["المحطة", "قراري", "ما لاحظته"]) if arch == "case_file" else None,
                               "verdict": (f"{M}Temporary verdict." if lang == "en" else f"{M}حكم مؤقت.") if arch == "case_file" else None,
                               "layers": layers},
                    "final_task": {"title": ("Final task" if lang == "en" else "المهمة النهائية"),
                                   "prompt": (f"{M}Temporary task." if lang == "en" else f"{M}مهمة مؤقتة."),
                                   "deliverable": {"title": ("Outcome" if lang == "en" else "الناتج"),
                                                   "columns": (["Item", "My answer"] if lang == "en" else ["البند", "إجابتي"]), "rows": ["", "", ""],
                                                   "model": [["-", "-"], ["-", "-"], ["-", "-"]]},
                                   "rubric": ([{"criterion": "Accuracy", "descriptor": "Answers are correct."},
                                               {"criterion": "Connection", "descriptor": "Every answer connects to the outcome."}] if lang == "en" else
                                              [{"criterion": "الدقة", "descriptor": "إجابات صحيحة."},
                                               {"criterion": "الربط", "descriptor": "يربط كل إجابة بالناتج."}])},
                    "reveal": {"title": ("Solution" if lang == "en" else "الحل"),
                               "story": (M + "This temporary reveal explains how the stage answers combine into the final outcome and is replaced by authored content."
                                         if lang == "en" else M + "كشف مؤقت يشرح كيف تجتمع إجابات المراحل في الناتج النهائي، يُستبدل بالنص الحقيقي."),
                               "reference": {"title": ("Concepts" if lang == "en" else "المفاهيم"),
                                             "items": (["Lesson concept"] if lang == "en" else [meta["goal_text"]])},
                               "plan": {"title": ("Plan" if lang == "en" else "الخطة"),
                                        "items": ([f"{M}Temporary action."] if lang == "en" else [f"{M}إجراء مؤقت."])}}}
        layers = (meta["project"]["payoff"].get("layers") or [None])
        eligible = [q for q in meta["questions"] if q.get("stage_eligible")]
        staged = eligible[:meta["n_stages"]]
        staged_ids = {q["id"] for q in staged}
        final = [q for q in meta["questions"] if q["id"] not in staged_ids]
        def display(q):
            if lang == "en":
                return {"question_ref": q["id"], "question_text": "Temporary question",
                        "choices": ([f"Option {chr(65 + i)}" for i in range(len(q.get("choices") or []))]
                                    if q["kind"] == "multiple_choice" else None),
                        "answer_text": "Temporary answer"}
            return {"question_ref": q["id"], "question_text": q["text"],
                    "choices": q.get("choices") if q["kind"] == "multiple_choice" else None,
                    "answer_text": q["answer"]}
        return {"stages": [{"question_ref": q["id"], "question_text": display(q)["question_text"],
                            "choices": display(q)["choices"], "answer_text": display(q)["answer_text"],
                            "title": (f"Stage {n}" if lang == "en" else f"المحطة {n}"),
                            "scene": (f"{M}Temporary scene." if lang == "en" else f"{M}مشهد مؤقت."),
                            "explanation": (f"{M}Temporary explanation." if lang == "en" else f"{M}تفسير مؤقت."),
                            "word_bank": (["Option one", "Option two"] if lang == "en" else ["خيار أ", "خيار ب"]) if q["kind"] == "complete" else None,
                            "finding": (f"{M}Finding {n}" if lang == "en" else f"{M}علامة {n}") if meta["topic"]["archetype"] == "case_file" else None,
                            "component": (f"{M}Component {n}" if lang == "en" else f"{M}قطعة {n}") if layers[0] else None,
                            "layer": layers[(n - 1) % len(layers)]}
                           for n, q in enumerate(staged, 1)],
                "final_questions": [display(q) for q in final]}
