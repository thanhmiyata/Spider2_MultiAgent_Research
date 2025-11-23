"""
Knowledge Retriever Agent for Spider 2.0 Domain Knowledge.

This module addresses the "Domain Knowledge" gap by providing business term definitions
and domain-specific concepts that are not apparent from database schema alone.
"""

import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class KnowledgeRetriever:
    """
    Retrieves domain knowledge and business definitions to enhance SQL generation.
    
    This addresses the challenge where complex business metrics (e.g., "Retention Rate",
    "Churn Rate", "Customer Lifetime Value") need specific calculation formulas that
    are not inherent in the database schema.
    """
    
    def __init__(self, glossary_path: Optional[str] = None):
        """
        Initialize the Knowledge Retriever.
        
        Args:
            glossary_path: Path to glossary file. If None, uses default location.
        """
        self.glossary_path = glossary_path
        self.glossary: Dict[str, str] = {}
        self._load_glossary()
    
    def _load_glossary(self):
        """Load glossary from file."""
        if not self.glossary_path:
            # Try default locations
            possible_paths = [
                Path(__file__).parent.parent.parent / "data" / "glossary.txt",
                Path(__file__).parent.parent / "data" / "glossary.txt",
                Path.cwd() / "data" / "glossary.txt",
            ]
            
            for path in possible_paths:
                if path.exists():
                    self.glossary_path = str(path)
                    break
        
        if not self.glossary_path or not Path(self.glossary_path).exists():
            print(f"[KnowledgeRetriever] Warning: Glossary file not found at {self.glossary_path}")
            return
        
        try:
            with open(self.glossary_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Parse glossary format: "Term: Definition" or "Term = Definition"
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Try both formats
                if ':' in line:
                    parts = line.split(':', 1)
                elif '=' in line:
                    parts = line.split('=', 1)
                else:
                    continue
                
                if len(parts) == 2:
                    term = parts[0].strip().lower()
                    definition = parts[1].strip()
                    self.glossary[term] = definition
            
            print(f"[KnowledgeRetriever] Loaded {len(self.glossary)} terms from glossary")
            
        except Exception as e:
            print(f"[KnowledgeRetriever] Error loading glossary: {e}")
    
    def search(self, question: str, threshold: int = 2) -> List[Tuple[str, str]]:
        """
        Search for relevant domain knowledge based on question.
        
        Args:
            question: User's natural language question
            threshold: Minimum word overlap to consider a match
            
        Returns: List of (term, definition) tuples for matched terms
        """
        if not self.glossary:
            return []
        
        question_lower = question.lower()
        matches = []
        
        for term, definition in self.glossary.items():
            # Direct substring match (most reliable)
            if term in question_lower:
                matches.append((term, definition))
                continue
            
            # Word-based matching for multi-word terms
            term_words = set(re.findall(r'\w+', term.lower()))
            question_words = set(re.findall(r'\w+', question_lower))
            
            # Calculate overlap
            overlap = len(term_words.intersection(question_words))
            
            # If enough words match and term is not too long, consider it a match
            if overlap >= threshold and overlap >= len(term_words) * 0.7:
                matches.append((term, definition))
        
        if matches:
            print(f"[KnowledgeRetriever] Found {len(matches)} relevant terms: {[t for t, _ in matches]}")
        
        return matches
    
    def format_knowledge_context(self, matches: List[Tuple[str, str]]) -> str:
        """
        Format matched terms into a context string for injection into prompts.
        
        Args:
            matches: List of (term, definition) tuples
            
        Returns: Formatted string with domain knowledge
        """
        if not matches:
            return ""
        
        lines = ["[Domain Knowledge]"]
        for term, definition in matches:
            lines.append(f"- {term.title()}: {definition}")
        
        return "\n".join(lines)
    
    def retrieve_and_inject(self, question: str) -> str:
        """
        Convenience method to search and format in one call.
        
        Args:
            question: User's question
            
        Returns: Formatted domain knowledge context (empty string if no matches)
        """
        matches = self.search(question)
        return self.format_knowledge_context(matches)
    
    def get_all_terms(self) -> List[str]:
        """Return all available terms in the glossary."""
        return list(self.glossary.keys())


def create_sample_glossary(output_path: str):
    """
    Create a sample glossary file with common business terms.
    
    Args:
        output_path: Path where glossary file should be created
    """
    sample_glossary = """# Spider 2.0 Domain Knowledge Glossary
# Format: Term: Definition or Term = Definition

# Customer Metrics
Retention Rate: Percentage of users who remain active from one period to the next. Formula: (users_active_today / users_active_yesterday) * 100
Churn Rate: Percentage of customers who stop using the service. Formula: (customers_lost / total_customers_at_start) * 100
Customer Lifetime Value: Total revenue expected from a customer over their lifetime. Formula: (average_purchase_value * purchase_frequency * customer_lifespan)
Active User: A user who has performed at least one significant action (login, purchase, etc.) within the specified time period

# Sales & Revenue Metrics
Revenue: Total income from sales. Formula: SUM(price * quantity)
Gross Profit: Revenue minus cost of goods sold. Formula: revenue - cost
Average Order Value: Average amount spent per order. Formula: total_revenue / number_of_orders
Conversion Rate: Percentage of visitors who make a purchase. Formula: (purchases / visits) * 100

# Time-based Metrics
Month-over-Month Growth: Percentage change from one month to the next. Formula: ((current_month - previous_month) / previous_month) * 100
Year-over-Year Growth: Percentage change from same period last year. Formula: ((current_year - previous_year) / previous_year) * 100
Moving Average: Average of values over a sliding time window. Formula: AVG(value) OVER (ORDER BY date ROWS BETWEEN n PRECEDING AND CURRENT ROW)

# Product & Inventory
Stock Turnover: Rate at which inventory is sold and replaced. Formula: cost_of_goods_sold / average_inventory
Out of Stock Rate: Percentage of time products are unavailable. Formula: (days_out_of_stock / total_days) * 100
Best Seller: Product with highest sales volume or revenue in a period

# Financial Metrics
Net Profit Margin: Profit as percentage of revenue. Formula: (net_profit / revenue) * 100
Return on Investment: Percentage return on an investment. Formula: ((gain_from_investment - cost_of_investment) / cost_of_investment) * 100

# E-commerce Specific
Cart Abandonment Rate: Percentage of carts not converted to orders. Formula: (carts_created - orders_completed) / carts_created * 100
Repeat Purchase Rate: Percentage of customers who buy again. Formula: (customers_with_multiple_orders / total_customers) * 100
"""
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(sample_glossary)
        print(f"[KnowledgeRetriever] Created sample glossary at {output_path}")
    except Exception as e:
        print(f"[KnowledgeRetriever] Error creating glossary: {e}")
