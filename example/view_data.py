"""
Simple script to view generated data from MongoDB collections.
"""
import sys
import json
from datetime import datetime

sys.path.append(".")
from clients.mongo_client import MongoDBClient

def format_datetime(dt):
    """Format datetime for display."""
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)

def view_collection_data(collection_name: str, limit: int = 5, uuid: str | None = None):
    """View data from a specific collection."""
    mongo_client = MongoDBClient()
    
    if not mongo_client.connect():
        print("❌ Failed to connect to MongoDB")
        return
    
    try:
        collection = mongo_client.storage_db[collection_name]
        query = {}
        if uuid:
            query['document_uuid'] = uuid
        documents = list(collection.find(query).limit(limit))
        
        print(f"\n📊 {collection_name.upper()} Collection ({len(documents)} documents shown):")
        print("=" * 60)
        
        for i, doc in enumerate(documents, 1):
            print(f"\n{i}. Document: {doc.get('filename', 'Unknown')}")
            print(f"   UUID: {doc.get('document_uuid', 'N/A')}")
            print(f"   Custom ID: {doc.get('custom_id', 'N/A')}")
            print(f"   Generated: {format_datetime(doc.get('generated_at'))}")
            
            # Show goals if available
            if 'goals' in doc:
                print(f"   Goals ({len(doc['goals'])}):")
                for j, goal in enumerate(doc['goals'][:3], 1):
                    print(f"     {j}. {goal[:60]}...")
                if len(doc['goals']) > 3:
                    print(f"     ... and {len(doc['goals']) - 3} more")
            
            # Show content overview based on collection type
            if collection_name == 'questions':
                questions_data = doc.get('questions', {})
                print(f"   Question Types:")
                for q_type in ['multiple_choice', 'short_answer', 'complete', 'true_false']:
                    count = len(questions_data.get(q_type, []))
                    if count > 0:
                        print(f"     {q_type}: {count}")
                
                # Show a sample question
                if questions_data.get('multiple_choice'):
                    sample_q = questions_data['multiple_choice'][0]
                    print(f"   Sample Question: {sample_q.get('question', '')[:80]}...")
                    if 'solution_outline' in sample_q and sample_q['solution_outline']:
                        outline = sample_q['solution_outline']
                        print(f"   Sample solution_outline: {outline[:120]}...")
                    if 'worked_solution' in sample_q and sample_q['worked_solution']:
                        ws = sample_q['worked_solution']
                        formula = ws.get('formula', '')
                        substitution = ws.get('substitution', '')
                        result = ws.get('result', '')
                        print("   Sample worked_solution:")
                        if formula:
                            print(f"     • formula: {formula[:100]}...")
                        if substitution:
                            print(f"     • substitution: {substitution[:100]}...")
                        if result:
                            print(f"     • result: {result[:100]}...")
            
            elif collection_name == 'worksheets':
                worksheet_data = doc.get('worksheet', {})
                print(f"   Worksheet Components:")
                for component in ['goals', 'applications', 'vocabulary', 'teacher_guidelines']:
                    count = len(worksheet_data.get(component, []))
                    if count > 0:
                        print(f"     {component}: {count} items")
            
            elif collection_name == 'summaries':
                summary_data = doc.get('summary', {})
                print(f"   Summary Components:")
                for component in ['opening', 'summary', 'ending']:
                    if component in summary_data:
                        content = summary_data[component][:100]
                        print(f"     {component}: {content}...")
            
            print(f"   Metadata: {doc.get('metadata', {}).get('generation_source', 'N/A')}")
            print("-" * 40)
    
    except Exception as e:
        print(f"❌ Error viewing collection {collection_name}: {str(e)}")
    
    finally:
        mongo_client.disconnect()

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="View generated data from MongoDB")
    parser.add_argument("--collection", choices=['questions', 'worksheets', 'summaries', 'all'],
                       default='all', help="Collection to view")
    parser.add_argument("--limit", type=int, default=5, help="Number of documents to show")
    parser.add_argument("--uuid", type=str, default=None, help="Filter by document UUID")
    
    args = parser.parse_args()
    
    print("📊 GENERATED DATA VIEWER")
    print("=" * 50)
    
    if args.collection == 'all':
        for collection in ['questions', 'worksheets', 'summaries']:
            view_collection_data(collection, args.limit, args.uuid)
    else:
        view_collection_data(args.collection, args.limit, args.uuid)
    
    print("\n✅ Data viewing completed!")

if __name__ == "__main__":
    main()
