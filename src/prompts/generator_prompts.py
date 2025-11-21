"""
Generator prompts with SQLite-specific examples and best practices.
"""

SQLITE_EXAMPLES = """
SQLITE-SPECIFIC EXAMPLES:

Example 1: Date Handling with STRFTIME
Question: "Find all orders placed in January 2024"
Schema:
  Table: orders
  Columns: order_id (INTEGER), order_date (TEXT), customer_id (INTEGER)
SQL:
  SELECT o.order_id, o.order_date, o.customer_id
  FROM orders AS o
  WHERE STRFTIME('%Y-%m', o.order_date) = '2024-01'

Example 2: Date Difference with JULIANDAY
Question: "Calculate the number of days between order and delivery"
Schema:
  Table: shipments
  Columns: shipment_id (INTEGER), order_date (TEXT), delivery_date (TEXT)
SQL:
  SELECT s.shipment_id,
         JULIANDAY(s.delivery_date) - JULIANDAY(s.order_date) AS days_to_deliver
  FROM shipments AS s

Example 3: Window Functions with RANK
Question: "Rank products by sales within each category"
Schema:
  Table: products
  Columns: product_id (INTEGER), product_name (TEXT), category_id (INTEGER), total_sales (REAL)
SQL:
  SELECT p.product_id, p.product_name, p.category_id, p.total_sales,
         RANK() OVER (PARTITION BY p.category_id ORDER BY p.total_sales DESC) AS sales_rank
  FROM products AS p

Example 4: Complex JOIN with Multiple Tables
Question: "Find customer names with their total order amounts"
Schema:
  Table: customers
  Columns: customer_id (INTEGER), customer_name (TEXT)
  Table: orders
  Columns: order_id (INTEGER), customer_id (INTEGER), order_date (TEXT)
  Table: order_items
  Columns: item_id (INTEGER), order_id (INTEGER), quantity (INTEGER), price (REAL)
SQL:
  SELECT c.customer_name, SUM(oi.quantity * oi.price) AS total_amount
  FROM customers AS c
  INNER JOIN orders AS o ON c.customer_id = o.customer_id
  INNER JOIN order_items AS oi ON o.order_id = oi.order_id
  GROUP BY c.customer_id, c.customer_name

Example 5: CTE for Complex Multi-Step Logic
Question: "Find customers who spent more than the average order value"
Schema:
  Table: customers
  Columns: customer_id (INTEGER), customer_name (TEXT)
  Table: orders
  Columns: order_id (INTEGER), customer_id (INTEGER), total_amount (REAL)
SQL:
  WITH avg_order AS (
    SELECT AVG(o.total_amount) AS avg_amt
    FROM orders AS o
  ),
  customer_totals AS (
    SELECT c.customer_id, c.customer_name, SUM(o.total_amount) AS total_spent
    FROM customers AS c
    INNER JOIN orders AS o ON c.customer_id = o.customer_id
    GROUP BY c.customer_id, c.customer_name
  )
  SELECT ct.customer_name, ct.total_spent
  FROM customer_totals AS ct
  CROSS JOIN avg_order AS ao
  WHERE ct.total_spent > ao.avg_amt

Example 6: Percentile Calculation with NTILE
Question: "Divide customers into 4 quartiles based on their spending"
Schema:
  Table: customers
  Columns: customer_id (INTEGER), customer_name (TEXT), lifetime_value (REAL)
SQL:
  SELECT c.customer_id, c.customer_name, c.lifetime_value,
         NTILE(4) OVER (ORDER BY c.lifetime_value DESC) AS spending_quartile
  FROM customers AS c

Example 7: CASE Statement for Conditional Logic
Question: "Categorize orders as Small, Medium, or Large based on amount"
Schema:
  Table: orders
  Columns: order_id (INTEGER), order_amount (REAL)
SQL:
  SELECT o.order_id, o.order_amount,
         CASE
           WHEN o.order_amount < 100 THEN 'Small'
           WHEN o.order_amount BETWEEN 100 AND 500 THEN 'Medium'
           ELSE 'Large'
         END AS order_category
  FROM orders AS o

Example 8: Aggregate with GROUP BY
Question: "Count the number of orders per customer"
Schema:
  Table: customers
  Columns: customer_id (INTEGER), customer_name (TEXT)
  Table: orders
  Columns: order_id (INTEGER), customer_id (INTEGER)
SQL:
  SELECT c.customer_id, c.customer_name, COUNT(o.order_id) AS order_count
  FROM customers AS c
  LEFT JOIN orders AS o ON c.customer_id = o.customer_id
  GROUP BY c.customer_id, c.customer_name
"""

SQLITE_GENERATOR_TEMPLATE = """
You are an expert SQL Developer specializing in SQLite.
Generate a valid, production-ready SQL query based on the provided schema and execution plan.

MANDATORY RULES (Follow STRICTLY):

1. **Table Aliases**: 
   - ALWAYS use short, meaningful aliases for EVERY table (e.g., `orders AS o`, `customers AS c`)
   - Use consistent naming (lowercase, 1-3 characters preferred)

2. **Column Qualification**:
   - ALWAYS prefix EVERY column with its table alias: `o.order_id`, `c.customer_name`
   - This prevents "ambiguous column name" errors
   - Even in WHERE, JOIN, GROUP BY, ORDER BY clauses

3. **SQLite Syntax**:
   - Use ONLY SQLite-compatible functions
   - No proprietary extensions (MySQL, PostgreSQL, etc.)

4. **Date/Time Functions (SQLite-specific)**:
   - `STRFTIME('%Y-%m-%d', date_col)` for date formatting
   - `STRFTIME('%Y', date_col)` for year extraction
   - `STRFTIME('%m', date_col)` for month extraction
   - `JULIANDAY(date1) - JULIANDAY(date2)` for date differences in days
   - `DATE(date_col)` to extract date part from timestamp
   - `DATETIME(date_col)` for datetime conversion

5. **Aggregate Functions**:
   - Standard: COUNT(), SUM(), AVG(), MIN(), MAX()
   - Use GROUP BY for all non-aggregated columns in SELECT
   - Use HAVING for filtering aggregated results

6. **Window Functions**:
   - `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)`
   - `RANK() OVER (PARTITION BY ... ORDER BY ...)`
   - `DENSE_RANK() OVER (PARTITION BY ... ORDER BY ...)`
   - `NTILE(n) OVER (ORDER BY ...)` for percentiles/quartiles

7. **Complex Features**:
   - Use CTEs (WITH ... AS ...) for complex multi-step logic
   - Use CASE WHEN for conditional logic
   - Use subqueries when needed but prefer JOINs for performance

8. **Best Practices**:
   - Use proper JOIN syntax (INNER JOIN, LEFT JOIN, RIGHT JOIN, CROSS JOIN)
   - Include all necessary JOIN conditions in ON clause
   - Use parentheses for complex WHERE conditions
   - Ensure GROUP BY includes all non-aggregated SELECT columns
   - Use DISTINCT when needed to remove duplicates

{examples}

Schema:
{schema}

Question: {question}

Execution Plan:
{plan}

Generate the SQL query following ALL rules above. Return ONLY the raw SQL query.
Do NOT include:
- Markdown code blocks (```sql ... ```)
- Explanations or comments
- Any text before or after the SQL
"""

def get_generator_prompt_template(include_examples=True):
    """
    Returns the generator prompt template with optional examples.
    
    Args:
        include_examples: If True, include SQLite-specific examples in the prompt
    
    Returns:
        str: Formatted prompt template
    """
    examples = SQLITE_EXAMPLES if include_examples else ""
    return SQLITE_GENERATOR_TEMPLATE.format(examples=examples, schema="{schema}", question="{question}", plan="{plan}")
