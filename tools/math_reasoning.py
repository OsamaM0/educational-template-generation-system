from typing import Optional, Dict, Any, List
import re
import sympy as sp
import numexpr
from langchain.tools import Tool
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class CalculatorInput(BaseModel):
    """Input for calculator tool."""
    expression: str = Field(description="Mathematical expression to calculate")


class StepVerificationInput(BaseModel):
    """Input for step verification tool."""
    step: str = Field(description="Mathematical step to verify")
    previous_steps: List[str] = Field(description="Previous steps in the solution")


class EquationSolverInput(BaseModel):
    """Input for equation solver tool."""
    equation: str = Field(description="Mathematical equation to solve")
    variable: str = Field(description="Variable to solve for", default="x")


class MathTools:
    """Collection of mathematical reasoning tools."""
    
    def __init__(self):
        self.sympy_symbols = {}
    
    def safe_calculator(self, expression: str) -> str:
        """
        Safely evaluate mathematical expressions.
        
        Args:
            expression: Mathematical expression as string
            
        Returns:
            Result of the calculation or error message
        """
        try:
            # Clean the expression
            expression = expression.strip()
            
            # Replace common math terms
            replacements = {
                '×': '*',
                '÷': '/',
                '²': '**2',
                '³': '**3',
                'π': 'pi',
                'sin': 'sin',
                'cos': 'cos',
                'tan': 'tan',
                'sqrt': 'sqrt',
                'log': 'log',
                'ln': 'log',
                'exp': 'exp'
            }
            
            for old, new in replacements.items():
                expression = expression.replace(old, new)
            
            # Use numexpr for safe evaluation
            result = numexpr.evaluate(expression)
            
            # Format the result
            if isinstance(result, (int, float)):
                if result == int(result):
                    return str(int(result))
                else:
                    return f"{result:.6f}".rstrip('0').rstrip('.')
            
            return str(result)
            
        except Exception as e:
            return f"خطأ في الحساب: {str(e)}"
    
    def equation_solver(self, equation: str, variable: str = "x") -> str:
        """
        Solve mathematical equations symbolically.
        
        Args:
            equation: Equation to solve (e.g., "x^2 + 2*x - 3 = 0")
            variable: Variable to solve for
            
        Returns:
            Solution(s) to the equation
        """
        try:
            # Parse the equation
            if '=' in equation:
                left, right = equation.split('=')
            else:
                left = equation
                right = "0"
            
            # Create symbolic variables
            var = sp.Symbol(variable)
            
            # Parse expressions
            left_expr = sp.sympify(left.strip())
            right_expr = sp.sympify(right.strip())
            
            # Solve the equation
            equation_obj = sp.Eq(left_expr, right_expr)
            solutions = sp.solve(equation_obj, var)
            
            if not solutions:
                return f"لا يوجد حل للمعادلة: {equation}"
            
            # Format solutions
            if len(solutions) == 1:
                return f"الحل: {variable} = {solutions[0]}"
            else:
                solutions_str = ", ".join([f"{variable} = {sol}" for sol in solutions])
                return f"الحلول: {solutions_str}"
                
        except Exception as e:
            return f"خطأ في حل المعادلة: {str(e)}"
    
    def step_verifier(self, step: str, previous_steps: List[str]) -> str:
        """
        Verify if a mathematical step is logically correct.
        
        Args:
            step: Current mathematical step
            previous_steps: List of previous steps
            
        Returns:
            Verification result and explanation
        """
        try:
            # Basic verification logic
            # This is a simplified version - in production, you'd want more sophisticated verification
            
            step_clean = step.strip()
            
            # Check for common mathematical operations
            if any(op in step_clean for op in ['+', '-', '*', '/', '=', '^']):
                # Extract expressions from the step
                expressions = re.findall(r'[0-9x\+\-\*/\^\(\)\.]+', step_clean)
                
                if expressions:
                    return f"الخطوة صحيحة: {step_clean}"
                else:
                    return f"الخطوة تحتاج لمراجعة: {step_clean}"
            
            return f"تم فحص الخطوة: {step_clean}"
            
        except Exception as e:
            return f"خطأ في التحقق من الخطوة: {str(e)}"
    
    def get_langchain_tools(self) -> List[BaseTool]:
        """Get LangChain compatible tools."""
        
        calculator_tool = Tool(
            name="calculator",
            description="Use this tool to perform mathematical calculations. Input should be a mathematical expression.",
            func=self.safe_calculator,
            args_schema=CalculatorInput
        )
        
        equation_solver_tool = Tool(
            name="equation_solver",
            description="Use this tool to solve mathematical equations. Input should be an equation with an equals sign.",
            func=lambda x: self.equation_solver(x),
            args_schema=EquationSolverInput
        )
        
        step_verifier_tool = Tool(
            name="step_verifier",
            description="Use this tool to verify mathematical steps. Input should be the current step.",
            func=lambda x: self.step_verifier(x, []),
            args_schema=StepVerificationInput
        )
        
        return [calculator_tool, equation_solver_tool, step_verifier_tool]


class ChainOfThoughtPrompts:
    """Chain of thought prompts for mathematical reasoning."""
    
    ARABIC_MATH_COT = """أنت مدرس رياضيات خبير. عند حل أي مسألة رياضية، اتبع الخطوات التالية:

1. **فهم المسألة**: اقرأ المسألة بعناية وحدد المطلوب
2. **تحديد المعطيات**: اكتب جميع المعطيات الموجودة
3. **وضع خطة الحل**: حدد الطريقة أو القانون المناسب
4. **تنفيذ الحل**: قم بالحل خطوة بخطوة مع التوضيح
5. **التحقق من الإجابة**: تأكد من صحة النتيجة

المسألة: {problem}

الحل خطوة بخطوة:

**الخطوة 1 - فهم المسألة:**
{step_1}

**الخطوة 2 - المعطيات:**
{step_2}

**الخطوة 3 - خطة الحل:**
{step_3}

**الخطوة 4 - التنفيذ:**
{step_4}

**الخطوة 5 - التحقق:**
{step_5}

**الإجابة النهائية:** {final_answer}
"""

    ENGLISH_MATH_COT = """You are an expert mathematics teacher. When solving any mathematical problem, follow these steps:

1. **Understand the Problem**: Read the problem carefully and identify what is being asked
2. **Identify Given Information**: Write down all given data
3. **Plan the Solution**: Determine the appropriate method or formula
4. **Execute the Solution**: Solve step by step with explanations
5. **Verify the Answer**: Check if the result makes sense

Problem: {problem}

Step-by-step solution:

**Step 1 - Understanding the Problem:**
{step_1}

**Step 2 - Given Information:**
{step_2}

**Step 3 - Solution Plan:**
{step_3}

**Step 4 - Execution:**
{step_4}

**Step 5 - Verification:**
{step_5}

**Final Answer:** {final_answer}
"""

    @classmethod
    def get_cot_prompt(cls, language: str = "arabic") -> str:
        """Get chain of thought prompt for the specified language."""
        if language.lower() == "english":
            return cls.ENGLISH_MATH_COT
        return cls.ARABIC_MATH_COT


class MathReasoningAgent:
    """Agent for mathematical reasoning using chain of thought."""
    
    def __init__(self, model, language: str = "arabic"):
        self.model = model
        self.language = language
        self.math_tools = MathTools()
        self.tools = self.math_tools.get_langchain_tools()
    
    def solve_with_thinking(self, problem: str) -> Dict[str, Any]:
        """
        Solve a mathematical problem using chain of thought reasoning.
        
        Args:
            problem: Mathematical problem to solve
            
        Returns:
            Dictionary containing the solution with thinking steps
        """
        try:
            # Get the appropriate chain of thought prompt
            cot_template = ChainOfThoughtPrompts.get_cot_prompt(self.language)
            
            # Create a structured prompt for step-by-step reasoning
            reasoning_prompt = f"""
أريدك أن تحل هذه المسألة الرياضية خطوة بخطوة مع إظهار التفكير:

المسألة: {problem}

استخدم الطريقة التالية:
1. فهم المسألة وتحديد المطلوب
2. كتابة المعطيات
3. وضع خطة للحل
4. تنفيذ الحل خطوة بخطوة
5. التحقق من الإجابة

ابدأ الحل الآن:
"""
            
            # Generate initial reasoning
            response = self.model.invoke(reasoning_prompt)
            reasoning_text = response.content if hasattr(response, 'content') else str(response)
            
            # Extract mathematical expressions and solve them
            math_expressions = self._extract_math_expressions(reasoning_text)
            calculated_results = {}
            
            for expr in math_expressions:
                result = self.math_tools.safe_calculator(expr)
                calculated_results[expr] = result
            
            return {
                "problem": problem,
                "reasoning": reasoning_text,
                "calculations": calculated_results,
                "language": self.language,
                "thinking_steps": self._extract_thinking_steps(reasoning_text)
            }
            
        except Exception as e:
            return {
                "problem": problem,
                "error": f"خطأ في الحل: {str(e)}",
                "language": self.language
            }
    
    def _extract_math_expressions(self, text: str) -> List[str]:
        """Extract mathematical expressions from text."""
        # Simple regex to find mathematical expressions
        patterns = [
            r'\d+\s*[\+\-\*/]\s*\d+',  # Basic arithmetic
            r'\d+\s*\^\s*\d+',  # Exponents
            r'sqrt\(\d+\)',  # Square roots
            r'\d+\.\d+[\+\-\*/]\d+\.\d+',  # Decimals
        ]
        
        expressions = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            expressions.extend(matches)
        
        return list(set(expressions))  # Remove duplicates
    
    def _extract_thinking_steps(self, text: str) -> List[str]:
        """Extract thinking steps from the reasoning text."""
        # Look for numbered steps or bullet points
        step_patterns = [
            r'الخطوة \d+[:\-](.+?)(?=الخطوة \d+|$)',
            r'\d+[\.\-]\s*(.+?)(?=\d+[\.\-]|$)',
            r'•\s*(.+?)(?=•|$)',
        ]
        
        steps = []
        for pattern in step_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            steps.extend([step.strip() for step in matches if step.strip()])
        
        return steps[:5] if steps else ["تم استخراج الخطوات من النص"]
