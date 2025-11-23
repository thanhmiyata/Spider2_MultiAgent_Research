"""
Tests for KnowledgeRetriever functionality.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agents.knowledge_retriever import KnowledgeRetriever, create_sample_glossary


class TestKnowledgeRetriever(unittest.TestCase):
    """Test knowledge retrieval functionality."""
    
    def setUp(self):
        """Create a temporary glossary for testing."""
        self.temp_glossary = tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, encoding='utf-8'
        )
        
        # Write test glossary
        test_content = """# Test Glossary
Retention Rate: Percentage of users remaining active. Formula: (users_active_today / users_active_yesterday) * 100
Churn Rate: Percentage of customers who stop using service
Revenue: Total income from sales. Formula: SUM(price * quantity)
Active User: User with at least one action in time period
Average Order Value: Average spent per order. Formula: total_revenue / number_of_orders
"""
        self.temp_glossary.write(test_content)
        self.temp_glossary.close()
        
        self.retriever = KnowledgeRetriever(glossary_path=self.temp_glossary.name)
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_glossary.name):
            os.unlink(self.temp_glossary.name)
    
    def test_glossary_loading(self):
        """Test that glossary is loaded correctly."""
        self.assertGreater(len(self.retriever.glossary), 0)
        self.assertIn('retention rate', self.retriever.glossary)
        self.assertIn('churn rate', self.retriever.glossary)
        self.assertIn('revenue', self.retriever.glossary)
    
    def test_direct_term_match(self):
        """Test exact term matching in questions."""
        question = "What is the retention rate for last month?"
        matches = self.retriever.search(question)
        
        self.assertGreater(len(matches), 0)
        # Should find retention rate
        terms_found = [term for term, _ in matches]
        self.assertIn('retention rate', terms_found)
    
    def test_multi_word_term_match(self):
        """Test matching of multi-word terms."""
        question = "Calculate the average order value for Q1"
        matches = self.retriever.search(question)
        
        self.assertGreater(len(matches), 0)
        terms_found = [term for term, _ in matches]
        self.assertIn('average order value', terms_found)
    
    def test_no_match(self):
        """Test when no terms match the question."""
        question = "How many products are in stock?"
        matches = self.retriever.search(question)
        
        # Should not match any terms
        self.assertEqual(len(matches), 0)
    
    def test_format_knowledge_context(self):
        """Test formatting of knowledge context."""
        matches = [
            ('retention rate', 'Percentage of users remaining active'),
            ('revenue', 'Total income from sales')
        ]
        
        formatted = self.retriever.format_knowledge_context(matches)
        
        self.assertIn('[Domain Knowledge]', formatted)
        self.assertIn('Retention Rate:', formatted)
        self.assertIn('Revenue:', formatted)
    
    def test_retrieve_and_inject(self):
        """Test combined search and format operation."""
        question = "What is the churn rate?"
        result = self.retriever.retrieve_and_inject(question)
        
        self.assertIn('[Domain Knowledge]', result)
        self.assertIn('Churn Rate:', result)
    
    def test_empty_result_formatting(self):
        """Test that empty matches return empty string."""
        matches = []
        formatted = self.retriever.format_knowledge_context(matches)
        self.assertEqual(formatted, "")
    
    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        question = "Calculate RETENTION RATE for users"
        matches = self.retriever.search(question)
        
        terms_found = [term for term, _ in matches]
        self.assertIn('retention rate', terms_found)
    
    def test_get_all_terms(self):
        """Test retrieval of all available terms."""
        terms = self.retriever.get_all_terms()
        
        self.assertGreater(len(terms), 0)
        self.assertIn('retention rate', terms)
        self.assertIn('revenue', terms)


class TestSampleGlossaryCreation(unittest.TestCase):
    """Test sample glossary creation."""
    
    def test_create_sample_glossary(self):
        """Test that sample glossary can be created."""
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False
        )
        temp_file.close()
        
        try:
            create_sample_glossary(temp_file.name)
            
            # Check file was created
            self.assertTrue(os.path.exists(temp_file.name))
            
            # Check content
            with open(temp_file.name, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.assertIn('Retention Rate', content)
            self.assertIn('Revenue', content)
            self.assertIn('Churn Rate', content)
            
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)


if __name__ == '__main__':
    unittest.main()
