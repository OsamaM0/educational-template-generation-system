"""
MongoDB client for fetching goals and storing generated templates.
"""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from typing import Dict, List, Any
from bson import ObjectId
from datetime import datetime

DEFAULT_MONGODB_URI = "mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ai?directConnection=true&serverSelectionTimeoutMS=2000&authSource=admin"

def short_idx(idx: Any) -> Any:
    """Return only the trailing segment of a composite idx.

    The document API returns hierarchical ids like
    '5141-5142-3-10-38-34372-34373-34376-1357'; only the last part
    ('1357') identifies the lesson itself.
    """
    if isinstance(idx, str) and '-' in idx:
        return idx.rsplit('-', 1)[-1]
    return idx


class MongoDBClient:
    """Client for MongoDB operations."""

    def __init__(self, connection_string: str = DEFAULT_MONGODB_URI):
        """
        Initialize MongoDB client.
        
        Args:
            connection_string: MongoDB connection string
        """
        self.connection_string = connection_string
        self.client = None
        self.goals_db = None  # For fetching goals from 'ien' database
        self.storage_db = None  # For storing results in 'ai' database
        
    def connect(self) -> bool:
        """
        Establish connection to MongoDB.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = MongoClient(self.connection_string)
            
            # Test connection
            self.client.admin.command('ping')
            
            # Setup databases
            self.goals_db = self.client['ien']  # For reading goals
            self.storage_db = self.client['ai']  # For storing results
            
            print("✅ MongoDB connection established")
            return True
            
        except ConnectionFailure as e:
            print(f"❌ MongoDB connection failed: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error connecting to MongoDB: {str(e)}")
            return False
    
    def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            print("🔒 MongoDB connection closed")
    
    def get_goals_by_custom_id(self, custom_id: str) -> List[Dict[str, Any]]:
        """
        Fetch goals for a lesson from the ien database using custom_id.

        Goals are resolved via lessons.lessonMapGoals -> lessonmappinggoals,
        the authoritative curriculum mapping (each lesson document carries an
        explicit array of its own goal ObjectIds). The legacy lessonplangoals
        collection (matched loosely by a 'lesson' field) is unreliable -- an
        audit found its 'lesson' associations wrong for every lesson checked
        where lessonMapGoals was also available -- so it's only used as a
        last-resort fallback when lessonMapGoals has nothing for this lesson.

        Args:
            custom_id: The custom_id to search for (equals the lesson's _id)

        Returns:
            List of goals or empty list if none found
        """
        if self.goals_db is None:
            print("❌ MongoDB not connected")
            return []

        if not ObjectId.is_valid(custom_id):
            # e.g. tahdiri lesson source ids ("719") are not ObjectIds -> no ien goals
            return []

        try:
            lesson_object_id = ObjectId(custom_id)

            # Primary source: lessons.lessonMapGoals -> lessonmappinggoals
            lesson_doc = self.goals_db['lessons'].find_one(
                {'_id': lesson_object_id}, {'lessonMapGoals': 1}
            )
            goal_ids = (lesson_doc or {}).get('lessonMapGoals') or []
            if goal_ids:
                goal_docs = list(self.goals_db['lessonmappinggoals'].find(
                    {'_id': {'$in': goal_ids}}
                ))
                goal_titles = [g['title'] for g in goal_docs if g.get('title')]
                if goal_titles:
                    print(f"📋 Found {len(goal_titles)} goals for custom_id: {custom_id} (lessonMapGoals)")
                    return goal_titles

            # Fallback: legacy lessonplangoals collection
            goals_cursor = self.goals_db['lessonplangoals'].find({
                'lesson': lesson_object_id
            })
            goal_titles = [g['title'] for g in goals_cursor if g.get('title')]
            print(f"📋 Found {len(goal_titles)} goals for custom_id: {custom_id} (lessonplangoals fallback)")
            return goal_titles

        except Exception as e:
            print(f"❌ Error fetching goals for custom_id {custom_id}: {str(e)}")
            return []
    
    def create_default_goals(self, document_content: str, count: int = 5) -> List[str]:
        """
        Create default goals when no goals are found in database.
        
        Args:
            document_content: Content to base goals on
            count: Number of goals to create
            
        Returns:
            List of default goals
        """
        # Simple goal templates based on content analysis
        default_goals = [
            "فهم المفاهيم الأساسية في النص",
            "تطبيق المعلومات المكتسبة في سياقات جديدة", 
            "تحليل العناصر الرئيسية في المحتوى",
            "تقييم الأفكار والمعلومات المطروحة",
            "إنتاج أعمال تعكس فهم المحتوى"
        ]
        
        print(f"🎯 Created {count} default goals")
        return default_goals[:count]
    
    def store_questions(self, document_data: Dict[str, Any], goals: List[str], 
                       questions: Dict[str, Any]) -> bool:
        """
        Store generated questions in MongoDB.
        
        Args:
            document_data: Original document data
            goals: Learning goals used
            questions: Generated questions
            
        Returns:
            True if storage successful, False otherwise
        """
        if self.storage_db is None:
            print("❌ MongoDB not connected")
            return False
        
        try:
            collection = self.storage_db['questions']
            
            record = {
                'document_uuid': document_data.get('uuid'),
                'document_idx': short_idx(document_data.get('idx')),
                'custom_id': document_data.get('custom_id'),
                'filename': document_data.get('filename'),
                'goals': goals,
                'questions': questions,
                'generated_at': datetime.utcnow(),
                'metadata': {
                    'generation_source': 'template_generator',
                    'goals_source': 'database' if len(goals) > 5 else 'default',
                    'content_length': len(document_data.get('content_without_image') or document_data.get('content') or '')
                }
            }
            
            # Use upsert to avoid duplicates
            result = collection.replace_one(
                {'document_uuid': document_data.get('uuid')},
                record,
                upsert=True
            )
            
            if result.upserted_id or result.modified_count > 0:
                print(f"✅ Questions stored for document: {document_data.get('filename')}")
                return True
            else:
                print(f"⚠️ No changes made for document: {document_data.get('filename')}")
                return False
                
        except Exception as e:
            print(f"❌ Error storing questions: {str(e)}")
            return False
    
    def store_worksheet(self, document_data: Dict[str, Any], goals: List[str], 
                       worksheet: Dict[str, Any]) -> bool:
        """
        Store generated worksheet in MongoDB.
        
        Args:
            document_data: Original document data
            goals: Learning goals used
            worksheet: Generated worksheet
            
        Returns:
            True if storage successful, False otherwise
        """
        if self.storage_db is None:
            print("❌ MongoDB not connected")
            return False
        
        try:
            collection = self.storage_db['worksheets']
            
            record = {
                'document_uuid': document_data.get('uuid'),
                'document_idx': short_idx(document_data.get('idx')),
                'custom_id': document_data.get('custom_id'),
                'filename': document_data.get('filename'),
                'goals': goals,
                'worksheet': worksheet,
                'generated_at': datetime.utcnow(),
                'metadata': {
                    'generation_source': 'template_generator',
                    'goals_source': 'database' if len(goals) > 5 else 'default',
                    'content_length': len(document_data.get('content_without_image') or document_data.get('content') or '')
                }
            }
            
            result = collection.replace_one(
                {'document_uuid': document_data.get('uuid')},
                record,
                upsert=True
            )
            
            if result.upserted_id or result.modified_count > 0:
                print(f"✅ Worksheet stored for document: {document_data.get('filename')}")
                return True
            else:
                print(f"⚠️ No changes made for document: {document_data.get('filename')}")
                return False
                
        except Exception as e:
            print(f"❌ Error storing worksheet: {str(e)}")
            return False
    
    def store_summary(self, document_data: Dict[str, Any], summary: Dict[str, Any]) -> bool:
        """
        Store generated summary in MongoDB.
        
        Args:
            document_data: Original document data
            summary: Generated summary
            
        Returns:
            True if storage successful, False otherwise
        """
        if self.storage_db is None:
            print("❌ MongoDB not connected")
            return False
        
        try:
            collection = self.storage_db['summaries']
            
            record = {
                'document_uuid': document_data.get('uuid'),
                'document_idx': short_idx(document_data.get('idx')),
                'custom_id': document_data.get('custom_id'),
                'filename': document_data.get('filename'),
                'summary': summary,
                'generated_at': datetime.utcnow(),
                'metadata': {
                    'generation_source': 'template_generator',
                    'content_length': len(document_data.get('content_without_image') or document_data.get('content') or '')
                }
            }
            
            result = collection.replace_one(
                {'document_uuid': document_data.get('uuid')},
                record,
                upsert=True
            )
            
            if result.upserted_id or result.modified_count > 0:
                print(f"✅ Summary stored for document: {document_data.get('filename')}")
                return True
            else:
                print(f"⚠️ No changes made for document: {document_data.get('filename')}")
                return False
                
        except Exception as e:
            print(f"❌ Error storing summary: {str(e)}")
            return False
    
    def store_mindmap(self, document_data: Dict[str, Any], mindmap: Dict[str, Any]) -> bool:
        """
        Store generated mind map in MongoDB.
        
        Args:
            document_data: Original document data
            mindmap: Generated mind map
            
        Returns:
            True if storage successful, False otherwise
        """
        if self.storage_db is None:
            print("❌ MongoDB not connected")
            return False
        
        try:
            collection = self.storage_db['mindmaps']
            
            record = {
                'document_uuid': document_data.get('uuid'),
                'document_idx': short_idx(document_data.get('idx')),
                'custom_id': document_data.get('custom_id'),
                'filename': document_data.get('filename'),
                'mindmap': mindmap,
                'generated_at': datetime.utcnow(),
                'metadata': {
                    'generation_source': 'template_generator',
                    'content_length': len(document_data.get('content_without_image') or document_data.get('content') or ''),
                    'node_count': len(mindmap.get('nodeDataArray', [])) if isinstance(mindmap, dict) else 0
                }
            }
            
            result = collection.replace_one(
                {'document_uuid': document_data.get('uuid')},
                record,
                upsert=True
            )
            
            if result.upserted_id or result.modified_count > 0:
                print(f"✅ Mind map stored for document: {document_data.get('filename')}")
                return True
            else:
                print(f"⚠️ No changes made for mind map: {document_data.get('filename')}")
                return False
                
        except Exception as e:
            print(f"❌ Error storing mind map: {str(e)}")
            return False
    
    def get_collection_stats(self) -> Dict[str, int]:
        """
        Get statistics for all collections.
        
        Returns:
            Dictionary with collection counts
        """
        stats = {}
        
        if self.storage_db is None:
            return stats
        
        try:
            for collection_name in ['questions', 'worksheets', 'summaries', 'mindmaps']:
                collection = self.storage_db[collection_name]
                count = collection.count_documents({})
                stats[collection_name] = count
                
        except Exception as e:
            print(f"❌ Error getting collection stats: {str(e)}")
        
        return stats
    
    def check_document_exists(self, document_uuid: str, template_type: str) -> bool:
        """
        Check if a document already has generated content of a specific type.
        
        Args:
            document_uuid: Document UUID to check
            template_type: Type of template ('questions', 'worksheets', 'summaries')
            
        Returns:
            True if document exists in collection, False otherwise
        """
        if self.storage_db is None:
            return False
        
        try:
            collection = self.storage_db[template_type]
            result = collection.find_one({'document_uuid': document_uuid})
            return result is not None
            
        except Exception as e:
            print(f"❌ Error checking document existence: {str(e)}")
            return False
