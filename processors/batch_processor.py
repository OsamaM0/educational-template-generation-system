"""
Batch processor for generating templates from multiple documents.
"""
import time
from typing import Dict, List, Any, Optional, Callable
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from clients.api_client import DocumentAPIClient
from clients.mongo_client import MongoDBClient
from generators.template_generator import TemplateGenerator
from models.storage_models import ProcessingStats, DocumentInfo

class BatchProcessor:
    """Handles batch processing of documents for template generation."""
    
    def __init__(self, api_client: DocumentAPIClient, mongo_client: MongoDBClient, 
                 template_generator: TemplateGenerator):
        """
        Initialize batch processor.
        
        Args:
            api_client: Document API client
            mongo_client: MongoDB client
            template_generator: Template generator instance
        """
        self.api_client = api_client
        self.mongo_client = mongo_client
        self.template_generator = template_generator
        self.stats = ProcessingStats()
        self._lock = threading.Lock()
    
    def process_all_documents(self, 
                            max_documents: Optional[int] = None,
                            page_size: int = 10,
                            start_page: int = 1,
                            template_types: List[str] = None,
                            skip_existing: bool = True,
                            max_workers: int = 1) -> ProcessingStats:
        """
        Process all documents and generate templates.
        
        Args:
            max_documents: Maximum number of documents to process
            page_size: Number of documents to fetch per page
            start_page: Page number to start fetching from (1-based)
            template_types: Types of templates to generate ['questions', 'worksheets', 'summaries']
            skip_existing: Skip documents that already have generated content
            max_workers: Number of parallel workers (1 for sequential processing)
            
        Returns:
            Processing statistics
        """
        if template_types is None:
            template_types = ['questions', 'worksheets', 'summaries', 'mindmaps']
        
        print(f"🚀 Starting batch processing...")
        print(f"📊 Template types: {template_types}")
        print(f"🔧 Max workers: {max_workers}")
        print(f"⏭️ Skip existing: {skip_existing}")
        
        # Fetch all documents
        documents = self.api_client.get_all_documents(
            page_size=page_size, 
            max_documents=max_documents,
            start_page=start_page
        )
        
        self.stats.total_documents = len(documents)
        
        if not documents:
            print("❌ No documents found")
            return self.stats
        
        print(f"📄 Processing {len(documents)} documents...")
        
        # Process documents
        if max_workers == 1:
            # Sequential processing
            self._process_documents_sequential(documents, template_types, skip_existing)
        else:
            # Parallel processing
            self._process_documents_parallel(documents, template_types, skip_existing, max_workers)
        
        self.stats.finish()
        self._print_final_stats()
        
        return self.stats
    
    def _process_documents_sequential(self, documents: List[Dict[str, Any]], 
                                    template_types: List[str], skip_existing: bool):
        """Process documents sequentially."""
        with tqdm(total=len(documents), desc="Processing documents") as pbar:
            for i, document in enumerate(documents):
                try:
                    self._process_single_document(document, template_types, skip_existing)
                    pbar.set_postfix({
                        'Current': document.get('filename', 'Unknown')[:30],
                        'Success': f"{self.stats.processed_documents}/{self.stats.total_documents}",
                        'Failed': self.stats.failed_documents
                    })
                except Exception as e:
                    print(f"❌ Error processing document {i+1}: {str(e)}")
                    self.stats.add_failure()
                finally:
                    pbar.update(1)
                    # Small delay to avoid overwhelming services
                    time.sleep(0.1)
    
    def _process_documents_parallel(self, documents: List[Dict[str, Any]], 
                                  template_types: List[str], skip_existing: bool, max_workers: int):
        """Process documents in parallel."""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(self._process_single_document, doc, template_types, skip_existing): doc 
                for doc in documents
            }
            
            # Process completed tasks
            with tqdm(total=len(documents), desc="Processing documents") as pbar:
                for future in as_completed(futures):
                    document = futures[future]
                    try:
                        future.result()
                        pbar.set_postfix({
                            'Success': f"{self.stats.processed_documents}/{self.stats.total_documents}",
                            'Failed': self.stats.failed_documents
                        })
                    except Exception as e:
                        print(f"❌ Error processing document {document.get('filename', 'Unknown')}: {str(e)}")
                        with self._lock:
                            self.stats.add_failure()
                    finally:
                        pbar.update(1)
    
    def _process_single_document(self, document_data: Dict[str, Any], 
                               template_types: List[str], skip_existing: bool):
        """
        Process a single document.
        
        Args:
            document_data: Document information
            template_types: Types of templates to generate
            skip_existing: Skip if document already processed
        """
        document_uuid = document_data.get('uuid')
        filename = document_data.get('filename', 'Unknown')
        custom_id = document_data.get('custom_id')
        collection_id = document_data.get('collection_id')
        content = document_data.get('content_without_image', '') or document_data.get('content', '')
        document_had_success = False  # track if at least one template stored successfully
        
        # Skip documents with specific collection IDs
        skip_collection_ids = [
            # 'd441cb83-1db7-472d-8ed7-43933399ad41',
            # '1f7c2e76-f61d-4f6d-8425-6a7f43ad80c1',
            # 'fabe3ac0-75a2-4765-995c-e6b94b7400e6',
            # 'f1c13718-f6f9-46d5-be8a-3fcea6a4daee'
        ]
        
        if collection_id in skip_collection_ids:
            print(f"⏭️ Skipping document {filename} - collection_id {collection_id} is in skip list")
            with self._lock:
                self.stats.add_skip()
            return
        
        if not content or len(content.strip()) < 20:
            print(f"⚠️ Skipping document with insufficient content length: {filename}")
            with self._lock:
                self.stats.add_skip()
            return
        
        # Check if we should skip existing documents
        if skip_existing:
            existing_types = []
            for template_type in template_types:
                collection_name = template_type if template_type.endswith('s') else f"{template_type}s"
                if self.mongo_client.check_document_exists(document_uuid, collection_name):
                    existing_types.append(template_type)
            
            if existing_types:
                remaining_types = [t for t in template_types if t not in existing_types]
                if not remaining_types:
                    print(f"⏭️ Skipping {filename} - all templates already exist")
                    with self._lock:
                        self.stats.add_skip()
                    return
                template_types = remaining_types
        
        # Enforce generation order: summary -> worksheet -> questions -> mindmap
        requested = set([t if t.endswith('s') else f"{t}s" for t in template_types])
        # If questions requested, also generate summary and worksheet as prerequisites
        if "questions" in requested:
            requested.update({"summaries", "worksheets"})
        ordered_types = [t for t in ["summaries", "worksheets", "questions", "mindmaps"] if t in requested]
        # Mark that we are attempting this document (if any ordered types)
        if ordered_types:
            with self._lock:
                self.stats.start_document_attempt()

        # Step 1: Summary
        summary_result = None
        if any(t in ordered_types for t in ["summaries"]):
            try:
                with self._lock:
                    self.stats.add_attempt("summaries")
                summary_result = self.template_generator.generate_summary(content=content)
                if self.mongo_client.store_summary(document_data, summary_result):
                    with self._lock:
                        self.stats.add_success("summaries")
                    document_had_success = True
                else:
                    print(f"⚠️ No changes made for summary: {filename}")
            except Exception as e:
                print(f"❌ Failed to generate summary for {filename}: {str(e)}")
                with self._lock:
                    self.stats.add_template_failure("summaries")

        # Step 2: Goals (DB -> AI)
        goals = []
        if custom_id:
            goals = self.mongo_client.get_goals_by_custom_id(custom_id)
        if not goals:
            # AI-generate goals from content (no default static list)
            try:
                goals = self.template_generator.content_processor.generate_learning_goals(content, count=5)
                print(f"🎯 AI-generated {len(goals)} goals")
            except Exception as e:
                print(f"❌ Failed to AI-generate goals, proceeding with empty goals: {str(e)}")
                goals = []

        # Step 3: Worksheet (may refine goals)
        worksheet_result = None
        if any(t in ordered_types for t in ["worksheets"]):
            try:
                with self._lock:
                    self.stats.add_attempt("worksheets")
                worksheet_result = self.template_generator.generate_worksheet(content=content, goals=goals)
                # Prefer structured goals if provided by template
                refined_goals = []
                if isinstance(worksheet_result, dict):
                    # If structured_goals present
                    structured = worksheet_result.get("structured_goals") or []
                    if structured and isinstance(structured, list):
                        for g in structured:
                            text = g.get("text") if isinstance(g, dict) else None
                            if text:
                                refined_goals.append(text)
                    # Fallback to flat goals in worksheet
                    if not refined_goals:
                        flat_goals = worksheet_result.get("goals")
                        if isinstance(flat_goals, list):
                            refined_goals = [str(x) for x in flat_goals if str(x).strip()]
                # Use refined goals if available
                if refined_goals:
                    goals = refined_goals
                if self.mongo_client.store_worksheet(document_data, goals, worksheet_result):
                    with self._lock:
                        self.stats.add_success("worksheets")
                    document_had_success = True
                else:
                    print(f"⚠️ No changes made for worksheet: {filename}")
            except Exception as e:
                print(f"❌ Failed to generate worksheet for {filename}: {str(e)}")
                with self._lock:
                    self.stats.add_template_failure("worksheets")

        # Step 4: Questions (use final goals; include math reasoning if analysis suggests)
        if any(t in ordered_types for t in ["questions"]):
            try:
                with self._lock:
                    self.stats.add_attempt("questions")
                questions_result = self.template_generator.generate_goal_based_questions(
                    content=content,
                    goals=goals,
                    question_counts={
                        "multiple_choice": 2,
                        "short_answer": 2,
                        "complete": 2,
                        "true_false": 2
                    },
                    difficulty_levels=[1, 2]
                )
                if self.mongo_client.store_questions(document_data, goals, questions_result):
                    with self._lock:
                        self.stats.add_success("questions")
                    document_had_success = True
                else:
                    print(f"⚠️ No changes made for questions: {filename}")
            except Exception as e:
                print(f"❌ Failed to generate questions for {filename}: {str(e)}")
                with self._lock:
                    self.stats.add_template_failure("questions")

        # Step 5: Mind Map
        if any(t in ordered_types for t in ["mindmaps"]):
            try:
                with self._lock:
                    self.stats.add_attempt("mindmaps")
                mindmap_result = self.template_generator.generate_mindmap(content=content)
                if self.mongo_client.store_mindmap(document_data, mindmap_result):
                    with self._lock:
                        self.stats.add_success("mindmaps")
                    document_had_success = True
                else:
                    print(f"⚠️ No changes made for mindmap: {filename}")
            except Exception as e:
                print(f"❌ Failed to generate mindmap for {filename}: {str(e)}")
                with self._lock:
                    self.stats.add_template_failure("mindmaps")

        # After all templates attempted, mark document processed if any success
        with self._lock:
            self.stats.mark_document_processed(document_had_success)
    
    def _get_goals_for_document(self, custom_id: str, content: str) -> List[str]:
        """Deprecated: goals now come from DB or AI; left for backward compatibility."""
        goals = []
        if custom_id:
            goals = self.mongo_client.get_goals_by_custom_id(custom_id)
        if not goals:
            try:
                goals = self.template_generator.content_processor.generate_learning_goals(content, count=5)
            except Exception:
                goals = []
        return goals
    
    def _generate_and_store_template(self, document_data: Dict[str, Any], 
                                   goals: List[str], template_type: str):
        """
        Generate and store a specific template type.
        
        Args:
            document_data: Document information
            goals: Learning goals
            template_type: Type of template to generate
        """
        content = document_data.get('content_without_image', '')

        # Generate template based on type
        if template_type == 'questions':
            result = self.template_generator.generate_goal_based_questions(
                content=content,
                goals=goals,
                question_counts={
                    "multiple_choice": 2,
                    "short_answer": 2,
                    "complete": 2,
                    "true_false": 2
                },
                difficulty_levels=[1, 2]
            )
            success = self.mongo_client.store_questions(document_data, goals, result)

        elif template_type == 'worksheets':
            result = self.template_generator.generate_worksheet(
                content=content,
                goals=goals
            )
            success = self.mongo_client.store_worksheet(document_data, goals, result)

        elif template_type == 'summaries':
            result = self.template_generator.generate_summary(content=content)
            success = self.mongo_client.store_summary(document_data, result)

        elif template_type == 'mindmaps':
            result = self.template_generator.generate_mindmap(content=content)
            success = self.mongo_client.store_mindmap(document_data, result)

        else:
            raise ValueError(f"Unknown template type: {template_type}")

        if not success:
            raise Exception(f"Failed to store {template_type} in database")
    
    def _print_final_stats(self):
        """Print final processing statistics."""
        stats_summary = self.stats.get_summary()
        
        print("\n" + "="*60)
        print("📊 BATCH PROCESSING COMPLETED")
        print("="*60)
        print(f"📄 Total Documents: {stats_summary['total_documents']}")
        print(f"✅ Processed: {stats_summary['processed_documents']}")
        if 'documents_attempted' in stats_summary:
            print(f"🛠️ Attempted: {stats_summary['documents_attempted']}")
        print(f"⏭️ Skipped: {stats_summary['skipped_documents']}")
        print(f"❌ Failed: {stats_summary['failed_documents']}")
        print(f"⏱️ Duration: {stats_summary['duration_seconds']:.1f} seconds")
        print(f"📈 Success Rate: {stats_summary['success_rate']:.1f}%")
        print()
        print("Generated Templates:")
        successful = stats_summary['successful_generations']
        print(f"  📝 Questions: {successful['questions']}")
        print(f"  📋 Worksheets: {successful['worksheets']}")
        print(f"  📄 Summaries: {successful['summaries']}")
        print(f"  🧠 Mind Maps: {successful['mindmaps']}")
        # Additional attempt/failure details if available
        attempts = stats_summary.get('template_attempts')
        failures = stats_summary.get('template_failures')
        if attempts and failures:
            print("Template Attempts vs Failures:")
            for t in ["summaries", "worksheets", "questions", "mindmaps"]:
                a = attempts.get(t, 0)
                f = failures.get(t, 0)
                s = successful.get(t, 0)
                print(f"  - {t.capitalize()}: attempts={a}, success={s}, failures={f}")
            total_attempts = sum(attempts.values())
            total_success = sum(successful.values())
            print(f"  Total: attempts={total_attempts}, success={total_success}, failures={total_attempts - total_success}")
            if stats_summary['documents_attempted']:
                print(f"Document Success Ratio: {stats_summary['processed_documents']}/{stats_summary['documents_attempted']} ({(stats_summary['processed_documents']/stats_summary['documents_attempted']*100):.1f}%)")
        print("="*60)
    
    def get_stats(self) -> ProcessingStats:
        """Get current processing statistics."""
        return self.stats
