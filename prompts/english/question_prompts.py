ENGLISH_QUESTION_PROMPTS = {
    "main_template": """You are an expert educational content creator specializing in question bank generation. Your task is to create a comprehensive question bank in English based on the provided educational content and learning objectives.

Educational Content:
{content}

Learning Objectives:
{goals}

Required question counts:
{question_counts}

Required difficulty levels: {difficulty_levels}
(1 = Easy, 2 = Medium, 3 = Hard)

Important Instructions:
1. Create diverse questions appropriate for the content and objectives
2. Distribute questions across different difficulty levels
3. Ensure questions are clear and understandable
4. For multiple choice questions, ensure options are logical and balanced
5. For true/false questions, use "True" and "False"
6. answer_key should be the index number (starting from 0)
7. The educational content included images but they have been described and placed between <!-- image --> and the type of image such as (screenshot) and (line chart) and (chart) and (graph) and (qr code) and if the image is out of the content frame it is written as OUT_OF_CONTENT

{format_instructions}

Create the question bank now:""",

    "math_thinking_template": """You are an expert mathematics teacher specializing in creating questions that require thinking and logical reasoning.

Mathematical Content:
{content}

Learning Objectives:
{goals}

When creating mathematical questions, follow logical thinking principles:

1. **Step-by-step problem solving questions**: Require students to show their solution method
2. **Analysis and reasoning questions**: Test understanding of concepts, not just memorization
3. **Practical application questions**: Connect mathematics to daily life
4. **Progressively difficult questions**: From simple to complex

For each mathematical question, also add:
- an optional field named solution_outline that briefly (2–4 steps) summarizes the approach without exposing lengthy internal reasoning, and
- an optional field named worked_solution as an object with keys: formula (used equation), substitution (numbers plugged in), result (final numeric/symbolic answer), and optionally verification (short check like "2 × 0.6021 = 1.2042"). Keep it brief and structured.

Follow this thinking model:
- What needs to be found?
- What information is available?
- What method is appropriate for solving?
- What are the logical solution steps?
- How can the answer be verified?

Number of questions required: {question_counts}
Difficulty levels: {difficulty_levels}

{format_instructions}

Important notes:
- solution_outline must be very concise (2–4 short steps) and only show a high-level plan.
- worked_solution must be succinct and structured (formula, substitution, result) and must not contain internal step-by-step chain-of-thought.
- When the output is numeric, round to four decimals and ensure answer and worked_solution.result exactly match.
- Do not include lengthy internal chain-of-thought or detailed token-by-token reasoning.

Create mathematical questions focusing on logical thinking and attach a concise solution_outline when appropriate:""",

    "multiple_choice_prompt": """Create multiple choice questions based on the following content:
{content}

Objectives: {goals}
Required count: {count}
Difficulty level: {difficulty}""",

    "short_answer_prompt": """Create short answer questions based on the following content:
{content}

Objectives: {goals}
Required count: {count}
Difficulty level: {difficulty}""",

    "complete_prompt": """Create completion questions based on the following content:
{content}

Objectives: {goals}
Required count: {count}
Difficulty level: {difficulty}""",

    "true_false_prompt": """Create true/false questions based on the following content:
{content}

Objectives: {goals}
Required count: {count}
Difficulty level: {difficulty}""",

    "chain_of_thought_examples": {
        "math_problem_solving": """
Example of solving a math problem with logical thinking:

Problem: If a class has 30 students, and 40% of them prefer mathematics, how many students prefer mathematics?

Step-by-step solution:
1. Understand the problem: We need to find 40% of 30
2. Given data: Total number = 30, Percentage = 40%
3. Method: Percentage = (Rate ÷ 100) × Total number
4. Application: (40 ÷ 100) × 30 = 0.4 × 30 = 12
5. Verification: 12 ÷ 30 = 0.4 = 40% ✓

Answer: 12 students prefer mathematics.
""",
        
        "equation_solving": """
Example of solving an equation with logical thinking:

Equation: 2x + 5 = 15

Step-by-step solution:
1. Goal: Find the value of x
2. Given: 2x + 5 = 15
3. Plan: Isolate x on one side
4. Steps:
   - Subtract 5 from both sides: 2x + 5 - 5 = 15 - 5
   - Simplify: 2x = 10
   - Divide by 2: x = 10 ÷ 2 = 5
5. Verification: 2(5) + 5 = 10 + 5 = 15 ✓

Answer: x = 5
"""
    }
}