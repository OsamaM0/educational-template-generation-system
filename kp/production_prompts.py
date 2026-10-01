"""Goal-first authorship. The supplied KP PDFs inform principles, not a template."""
import json

def j(value):
    return json.dumps(value, ensure_ascii=False)

SYSTEM = '''You author knowledge production (الإنتاج المعرفي): a useful, accurate,
shareable educational resource that explains, organizes, applies, or develops
knowledge for a defined audience and purpose. It can be a finished teaching
resource or a meaningful learner-created product. It is not necessarily a game,
a worksheet, a sequence of questions, or a project with a final reveal.
Start with the actual lesson content and worksheet goal. Choose a form because
it serves that goal, then write the resource itself, not merely directions to
make it. product_type is an open description, not a closed menu.
Reference examples illustrate breadth: concise explanations, comparisons,
concept maps, annotated worked examples, stories that explain a rule, curated
teaching resources, interactive cards, practical guides, and professional
portfolios. These are examples, not mandatory types or layouts. Other forms
are welcome when justified by the lesson. A game is appropriate only when its
mechanics directly teach the goal. Never add cybersecurity, investigations,
secret letters, passwords, rewards, generic missions, or unrelated metaphors
unless the lesson and educational purpose actually warrant them.
Products for different goals should differ in educational purpose, treatment,
and organization when the goals warrant it; do not just rename one template.
Do not force artificial variety when one form is genuinely best. No mandatory
cover, introduction, rules, four stages, payoff, final table, rubric, or reveal.
Questions from the supplied bank are optional: select only directly relevant
items when practice/checking serves this resource. Zero questions is valid.
Start from question_refs=[]; do not fill a quota or select questions just because
they are available. The resource's actual knowledge is the main product, with
questions used sparingly if they add a purposeful check. Respect max_questions.
No minimum question count. Do not invent bank question IDs. Authoring new
worked examples, dialogues, activities, and explanations is welcome, but do
not pretend those are bank questions. Do not reproduce unrelated topics,
logos, author biographies, or instructions from reference documents. Do not
invent external links, QR codes, research results, classroom observations,
or claim a proposed intervention was actually conducted.
Ground every section in the supplied content and goal, using accurate examples
of the same concepts. Make the finished resource useful independently of an
answer key: write substantive rules, explanations, comparisons, model dialogues,
worked calculations, annotated corrections, or another finished treatment that
teaches the goal. Generic introductions about the importance of learning,
directions alone, lists of unexplained errors, and congratulatory conclusions
do not constitute the product. Provide the actual explanation or model.
Check boundary cases as well as ordinary cases: for example, a fractional part
equal to one also needs regrouping, not just a fractional part greater than one.
Do not refer to images, videos, audio, cards or other assets that are absent.
If a source mentions an unavailable visual, provide a self-contained scene,
schematic or labelled table instead of telling learners to inspect a missing
image. Clearly identify a textual scene when no image is supplied.
Use explicit \\( ... \\) delimiters for mathematical expressions,
especially signed fractions; express steps and explain reasoning correctly.
Keep content concise enough to print cleanly; no HTML or raw markdown tables.
Return the requested structured JSON. Unused nullable block fields must be null.
'''

def base(content, title, lang):
    language = ('All authored visible text MUST be English, even if source metadata or questions are Arabic. Translate faithfully.'
                if lang == 'en' else 'All authored visible text MUST be Arabic; technical notation and necessary quoted examples may retain their language.')
    return [{'role':'system','content':SYSTEM + '\n' + language},
            {'role':'user','content':f'Lesson: {title}\nSource lesson content:\n{content}'}]

def topics(goals, subject):
    return f'''Plan exactly one useful knowledge product per supplied worksheet goal.
Subject: {subject}. Goals and optional question candidates:\n{j(goals)}
For each topic name the actual product_type freely, give a specific title,
audience, educational purpose, concepts, and explain lesson_connection: why this
form teaches THIS goal. layout is presentation only: document for flowing
explanations/tables, cards for modular resources, poster for a compact overview.
Choose question_refs freely from that goal's candidates, including []. Keep
products distinguishable by their learning function rather than cosmetic names.
'''

def project(goal, topic, questions):
    return f'''Write the COMPLETE product for goal {j(goal)}. Approved plan: {j(topic)}.
Optional selected bank questions: {j(questions)}.
Organize sections in the order this particular product needs. Use descriptive
section titles and free-form role labels, not a fixed sequence. A resource can
be one compact section or several sections. No compulsory learner assignment.
Each block uses the appropriate primitive: paragraph/callout (text), bullets/
steps/cards (items), table (columns and rows with cells), question (question_ref),
response_space (text describing a useful learner response). Use tables for
comparisons, steps for worked reasoning, cards for reusable snippets; stories
and dialogues can be paragraphs or tables. Do not make everything paragraphs.
Each card item must contain a finished fact, explanation or example; empty cards
are not knowledge. Put blank learner responses in response_space blocks instead.
For question blocks use each selected ID exactly once. Use no other IDs.
Represent those IDs as question blocks, never only in card titles or text.
When question_refs is empty, include no question blocks. Write worked examples
as authored explanation blocks, not disguised answer-bank items. Mark answer
keys or teacher-only implementation notes teacher_only=true; ordinary explained
examples and finished reference material remain visible to learners.
Aim for 2–5 concise sections and approximately 300–600 words when useful, or a
shorter compact poster/cards. Never pad the output to a fixed section count.
'''

def links(questions):
    return f'''Provide faithful display text in the product language for these selected
bank questions, exactly once each: {j(questions)}. Preserve meaning, mathematical
values, option order and option count. choices is non-null only for multiple
choice. Answer_text for multiple choice must match the correct option. Explain
the correct answer briefly. Do not add letters, tokens, story mechanics or new
questions. Use explicit math delimiters for signed fractions.
'''
