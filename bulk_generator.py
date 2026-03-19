"""
Bulk Template Generator - Main orchestration script for processing all documents.

This script:
1. Fetches documents from the API
2. Retrieves goals from MongoDB using custom_id
3. Generates questions, worksheets, and summaries
4. Stores results in MongoDB

Usage:
    python bulk_generator.py --help
    python bulk_generator.py --max-docs 100 --templates questions worksheets
    python bulk_generator.py --page-size 20 --skip-existing
"""

import os
import sys
import json
import argparse
from typing import List, Optional

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.api_client import DocumentAPIClient
from clients.mongo_client import MongoDBClient
from generators.template_generator import TemplateGenerator
from processors.batch_processor import BatchProcessor
from config.settings import Settings

def validate_environment():
    """Validate that all required environment variables and configs are set."""
    try:
        Settings.validate_config()
        print("✅ Environment validation passed")
        return True
    except Exception as e:
        print(f"❌ Environment validation failed: {str(e)}")
        print("\n💡 Make sure to:")
        print("   1. Set OPENAI_API_KEY environment variable")
        print("   2. Install requirements: pip install -r requirements.txt")
        return False

def test_connections(api_client: DocumentAPIClient, mongo_client: MongoDBClient) -> bool:
    """Test API and database connections."""
    print("🔍 Testing connections...")
    
    # Test API connection
    if not api_client.validate_connection():
        print("❌ API connection failed")
        return False
    print("✅ API connection successful")
    
    # Test MongoDB connection
    if not mongo_client.connect():
        print("❌ MongoDB connection failed")
        return False
    print("✅ MongoDB connection successful")
    
    return True

def print_collection_stats(mongo_client: MongoDBClient):
    """Print current collection statistics."""
    stats = mongo_client.get_collection_stats()
    if stats:
        print("\n📊 Current Collection Stats:")
        for collection, count in stats.items():
            print(f"   {collection}: {count} documents")
    else:
        print("\n📊 No collection stats available")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Bulk Template Generator - Process documents and generate educational templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process first 50 documents, generate all template types
  python bulk_generator.py --max-docs 50
  
  # Generate only questions and worksheets, skip existing
  python bulk_generator.py --templates questions worksheets --skip-existing
  
  # Generate only mind maps for all documents
  python bulk_generator.py --templates mindmaps
  
  # Use larger page size for faster fetching
  python bulk_generator.py --page-size 50 --max-docs 200
  
  # Start from page 5 with page size 20 (skip first 80 documents)
  python bulk_generator.py --start-page 5 --page-size 20 --max-docs 100
  
  # Process documents 201-300 (page 11-15 with page size 20)
  python bulk_generator.py --start-page 11 --page-size 20 --max-docs 100
  
  # Parallel processing (experimental)
  python bulk_generator.py --workers 3 --max-docs 100
  
    # Process a single document by UUID
    python bulk_generator.py --uuid 1487b3f2-c91f-4fe8-b58e-59330058fcfa --templates questions summaries mindmaps
  
    # Process multiple documents from a UUID file
    python bulk_generator.py --uuid-file doc_ids.json --templates questions summaries mindmaps
        """
    )
    
    # Processing options
    parser.add_argument("--max-docs", type=int, default=None,
                       help="Maximum number of documents to process (default: all)")
    parser.add_argument("--page-size", type=int, default=10,
                       help="Number of documents to fetch per API call (default: 10)")
    parser.add_argument("--start-page", type=int, default=1,
                       help="Page number to start fetching from (default: 1)")
    parser.add_argument("--templates", nargs="+", 
                       choices=["questions", "worksheets", "summaries", "mindmaps"],
                       default=["questions", "worksheets", "summaries", "mindmaps"],
                       help="Template types to generate (default: all)")
    parser.add_argument("--skip-existing", action="store_true",
                       help="Skip documents that already have generated templates")
    parser.add_argument("--workers", type=int, default=1,
                       help="Number of parallel workers (default: 1, sequential)")
    parser.add_argument("--uuid", dest="document_uuid", type=str, default=None,
                       help="Process a single document by UUID; overrides pagination options")
    parser.add_argument("--uuid-file", dest="uuid_file", type=str, default=None,
                       help="Path to a JSON file containing a list of document UUIDs to process")
    
    # Connection options
    parser.add_argument("--api-url", default="http://65.109.31.94:8080",
                       help="API base URL")
    parser.add_argument("--mongo-url", 
                       default="mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ai?directConnection=true&serverSelectionTimeoutMS=2000&authSource=admin",
                       help="MongoDB connection string")
    
    # Utility options
    parser.add_argument("--test-connection", action="store_true",
                       help="Test connections and exit")
    parser.add_argument("--stats", action="store_true",
                       help="Show collection statistics and exit")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simulate processing without making changes")
    
    args = parser.parse_args()
    
    print("🚀 BULK TEMPLATE GENERATOR")
    print("=" * 50)
    
    # Validate environment
    if not validate_environment():
        return 1
    
    # Initialize clients
    print("\n🔧 Initializing clients...")
    try:
        api_client = DocumentAPIClient(base_url=args.api_url)
        mongo_client = MongoDBClient(connection_string=args.mongo_url)
        template_generator = TemplateGenerator()
        
    except Exception as e:
        print(f"❌ Failed to initialize clients: {str(e)}")
        return 1
    
    # Test connections
    if not test_connections(api_client, mongo_client):
        return 1
    
    # Handle utility options
    if args.stats:
        print_collection_stats(mongo_client)
        mongo_client.disconnect()
        return 0
    
    if args.test_connection:
        print("✅ All connections successful!")
        mongo_client.disconnect()
        return 0
    
    try:
        # Print processing configuration
        print(f"\n📋 Processing Configuration:")
        mode = 'Single Document' if args.document_uuid else ('UUID File' if args.uuid_file else 'Batch')
        print(f"   Mode: {mode}")
        if args.document_uuid:
            print(f"   Document UUID: {args.document_uuid}")
        if args.uuid_file:
            print(f"   UUID File: {args.uuid_file}")
        print(f"   Max Documents: {args.max_docs or 'All'}")
        print(f"   Page Size: {args.page_size}")
        print(f"   Start Page: {args.start_page}")
        if args.start_page > 1:
            skip_count = (args.start_page - 1) * args.page_size
            print(f"   Skipping first: {skip_count} documents")
        print(f"   Template Types: {', '.join(args.templates)}")
        print(f"   Skip Existing: {args.skip_existing}")
        print(f"   Workers: {args.workers}")
        print(f"   Dry Run: {args.dry_run}")
        
        # Single document mode
        if args.document_uuid:
            if args.dry_run:
                print("\n🏃‍♂️ DRY RUN MODE - No changes will be made")
                doc = api_client.get_document_by_uuid(args.document_uuid)
                if not doc:
                    print(f"❌ Document not found: {args.document_uuid}")
                    return 1
                name = doc.get('filename') or doc.get('uuid') or 'Unknown'
                print(f"\n📊 Would process 1 document: {name}")
                print("✅ Dry run completed")
                return 0
            
            # Show current stats before processing
            print_collection_stats(mongo_client)

            print(f"\n🎯 Processing single document {args.document_uuid}...")
            doc = api_client.get_document_by_uuid(args.document_uuid)
            if not doc:
                print(f"❌ Document not found: {args.document_uuid}")
                return 1

            # Use BatchProcessor internals for consistency
            batch_processor = BatchProcessor(
                api_client=api_client,
                mongo_client=mongo_client,
                template_generator=template_generator
            )
            batch_processor.stats.total_documents = 1
            try:
                batch_processor._process_single_document(doc, args.templates, args.skip_existing)
            except Exception as e:
                print(f"❌ Error processing document {args.document_uuid}: {str(e)}")
                batch_processor.stats.add_failure()
            finally:
                batch_processor.stats.finish()
                batch_processor._print_final_stats()

            print_collection_stats(mongo_client)
            print("\n🎉 Single document processing completed!")
            return 0

        # UUID file mode
        if args.uuid_file:
            # Load and validate UUIDs from file
            if not os.path.isfile(args.uuid_file):
                print(f"❌ UUID file not found: {args.uuid_file}")
                return 1
            
            with open(args.uuid_file, 'r', encoding='utf-8') as f:
                uuid_list = json.load(f)
            
            if not isinstance(uuid_list, list) or not all(isinstance(u, str) for u in uuid_list):
                print("❌ UUID file must contain a JSON array of UUID strings")
                return 1
            
            print(f"\n📂 Loaded {len(uuid_list)} UUIDs from {args.uuid_file}")
            
            if args.dry_run:
                print("\n🏃‍♂️ DRY RUN MODE - No changes will be made")
                print(f"📊 Would process {len(uuid_list)} documents")
                print("✅ Dry run completed")
                return 0
            
            # Show current stats before processing
            print_collection_stats(mongo_client)
            
            # Fetch documents by UUID and process
            print(f"\n🎯 Fetching and processing {len(uuid_list)} documents from UUID file...")
            documents = []
            not_found = []
            for uid in uuid_list:
                doc = api_client.get_document_by_uuid(uid)
                if doc:
                    documents.append(doc)
                else:
                    not_found.append(uid)
            
            if not_found:
                print(f"⚠️ {len(not_found)} UUIDs not found and will be skipped:")
                for uid in not_found:
                    print(f"   - {uid}")
            
            if not documents:
                print("❌ No valid documents found from UUID file")
                return 1
            
            print(f"📄 Processing {len(documents)} documents...")
            
            batch_processor = BatchProcessor(
                api_client=api_client,
                mongo_client=mongo_client,
                template_generator=template_generator
            )
            batch_processor.stats.total_documents = len(documents)
            
            if args.workers == 1:
                batch_processor._process_documents_sequential(documents, args.templates, args.skip_existing)
            else:
                batch_processor._process_documents_parallel(documents, args.templates, args.skip_existing, args.workers)
            
            batch_processor.stats.finish()
            batch_processor._print_final_stats()
            
            print_collection_stats(mongo_client)
            print("\n🎉 UUID file processing completed!")
            return 0

        if args.dry_run:
            print("\n🏃‍♂️ DRY RUN MODE - No changes will be made")
            # In dry run, just fetch and count documents
            documents = api_client.get_all_documents(
                page_size=args.page_size,
                max_documents=args.max_docs,
                start_page=args.start_page
            )
            print(f"\n📊 Would process {len(documents)} documents")
            print("✅ Dry run completed")
            return 0
        
        # Show current stats before processing
        print_collection_stats(mongo_client)
        
        # Initialize batch processor
        batch_processor = BatchProcessor(
            api_client=api_client,
            mongo_client=mongo_client,
            template_generator=template_generator
        )
        
        # Process documents
        print(f"\n🎯 Starting bulk processing...")
        stats = batch_processor.process_all_documents(
            max_documents=args.max_docs,
            page_size=args.page_size,
            start_page=args.start_page,
            template_types=args.templates,
            skip_existing=args.skip_existing,
            max_workers=args.workers
        )
        
        # Show final stats
        print_collection_stats(mongo_client)
        
        print("\n🎉 Bulk processing completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Processing interrupted by user")
        print("📊 Partial statistics:")
        if 'batch_processor' in locals():
            stats = batch_processor.get_stats()
            print(f"   Processed: {stats.processed_documents}/{stats.total_documents}")
            print(f"   Failed: {stats.failed_documents}")
        return 1
        
    except Exception as e:
        print(f"\n❌ Processing failed: {str(e)}")
        return 1
        
    finally:
        # Clean up connections
        if 'mongo_client' in locals():
            mongo_client.disconnect()
        print("🔒 Connections closed")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
