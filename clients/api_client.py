"""
API client for fetching documents from the document service.
"""
import requests
from typing import Dict, List, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import time

class DocumentAPIClient:
    """Client for interacting with the document API."""
    
    def __init__(self, base_url: str = "http://65.109.31.94:8080"):
        """
        Initialize the API client.
        
        Args:
            base_url: Base URL for the API
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'accept': 'application/json',
            'User-Agent': 'TemplateGenerator/1.0'
        })
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def get_documents(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """
        Fetch documents from the API with pagination.
        
        Args:
            page: Page number (1-based)
            page_size: Number of documents per page
            
        Returns:
            API response containing documents and pagination info
            
        Raises:
            requests.RequestException: If API call fails
        """
        url = f"{self.base_url}/documents/"
        params = {
            'page': page,
            'page_size': page_size
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"❌ Error fetching documents (page {page}): {str(e)}")
            raise
    
    def get_all_documents(self, page_size: int = 10, max_documents: Optional[int] = None, start_page: int = 1) -> List[Dict[str, Any]]:
        """
        Fetch all documents using pagination.
        
        Args:
            page_size: Number of documents per page
            max_documents: Maximum number of documents to fetch (None for all)
            start_page: Page number to start fetching from (1-based)
            
        Returns:
            List of all documents
        """
        all_documents = []
        page = start_page
        
        print(f"🔄 Starting to fetch documents (page_size: {page_size}, start_page: {start_page})")
        
        if start_page > 1:
            skip_count = (start_page - 1) * page_size
            print(f"⏭️ Skipping first {skip_count} documents (starting from page {start_page})")
        
        while True:
            try:
                # Add small delay between requests
                if page > start_page:
                    time.sleep(0.5)
                
                response = self.get_documents(page=page, page_size=page_size)
                documents = response.get('items', [])
                
                if not documents:
                    break
                
                all_documents.extend(documents)
                
                print(f"📄 Fetched page {page}: {len(documents)} documents "
                      f"(Total fetched: {len(all_documents)}, API Total: {response.get('total', '?')})")
                
                # Check if we've reached the max limit
                if max_documents and len(all_documents) >= max_documents:
                    all_documents = all_documents[:max_documents]
                    print(f"🛑 Reached maximum document limit: {max_documents}")
                    break
                
                # Check if this is the last page
                if not response.get('has_next', False):
                    break
                
                page += 1
                
            except Exception as e:
                print(f"❌ Error fetching page {page}: {str(e)}")
                break
        
        print(f"✅ Total documents fetched: {len(all_documents)}")
        return all_documents
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def get_document_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific document by UUID using the direct endpoint.

        Args:
            uuid: Document UUID

        Returns:
            Document data as a dict, or None if not found (404)
        """
        url = f"{self.base_url}/documents/{uuid}"
        try:
            response = self.session.get(url)
            # Return None if the document isn't found; don't retry on 404
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"❌ Error fetching document {uuid}: {str(e)}")
            # Re-raise to trigger retry for transient errors
            raise
    
    def validate_connection(self) -> bool:
        """
        Test the API connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            response = self.get_documents(page=1, page_size=1)
            return True
        except Exception as e:
            print(f"❌ API connection failed: {str(e)}")
            return False
