#!/usr/bin/env python3
"""
Enhanced Template Generation Example with Mathematical Thinking Features

This example demonstrates the new thinking capabilities added to the template generation system,
especially optimized for mathematical content (رياضة).

Features demonstrated:
1. Chain-of-thought reasoning for math problems
2. Mathematical tools integration (calculator, equation solver)
3. Enhanced content analysis for mathematical topics
4. Step-by-step problem solving guidance
5. Improved question generation with logical thinking
"""

import sys
import os
import json
from pathlib import Path

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ..generators.template_generator import TemplateGenerator
from ..tools.math_reasoning import MathReasoningAgent, MathTools, ChainOfThoughtPrompts

def load_sample_content():
    """Load sample mathematical content."""
    content_file = Path(__file__).parent / "sample_math_content.txt"
    if content_file.exists():
        with open(content_file, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        # Fallback content
        return """
الرياضيات - حل المعادلات الخطية

المعادلة الخطية هي معادلة من الدرجة الأولى.
مثال: 2x + 5 = 15

خطوات الحل:
1. طرح 5 من الطرفين
2. القسمة على 2
3. الحصول على x = 5

تطبيق: إذا كان عدد التفاح في السلة مضروباً في 3 مضافاً إليه 7 يساوي 22، فكم تفاحة في السلة؟
الحل: 3x + 7 = 22
"""

def demonstrate_math_tools():
    """Demonstrate mathematical reasoning tools."""
    print("🧮 Mathematical Tools Demonstration")
    print("=" * 50)
    
    math_tools = MathTools()
    
    # Test calculator
    print("\n1. Calculator Tool:")
    expressions = ["2 + 3 * 4", "sqrt(16)", "10^2", "15 / 3"]
    for expr in expressions:
        result = math_tools.safe_calculator(expr)
        print(f"   {expr} = {result}")
    
    # Test equation solver
    print("\n2. Equation Solver:")
    equations = ["2*x + 5 - 15", "x^2 - 4", "3*x - 12"]
    for eq in equations:
        result = math_tools.equation_solver(eq)
        print(f"   {eq} = 0 → {result}")
    
    # Test step verification
    print("\n3. Step Verification:")
    steps = [
        "2x + 5 = 15",
        "2x = 15 - 5",
        "2x = 10",
        "x = 5"
    ]
    for step in steps:
        result = math_tools.step_verifier(step, [])
        print(f"   {result}")

def demonstrate_chain_of_thought():
    """Demonstrate chain of thought reasoning."""
    print("\n🧠 Chain of Thought Reasoning Demo")
    print("=" * 50)
    
    # Sample math problem
    problem = "إذا كان عمر أحمد ضعف عمر سارة، ومجموع عمريهما 36 سنة، فما عمر كل منهما؟"
    
    try:
        # This would require a real OpenAI API key
        print(f"\nProblem: {problem}")
        print("\nChain of Thought Template (Arabic):")
        print(ChainOfThoughtPrompts.get_cot_prompt("arabic")[:500] + "...")
        
        print("\nChain of Thought Template (English):")
        print(ChainOfThoughtPrompts.get_cot_prompt("english")[:500] + "...")
        
    except Exception as e:
        print(f"Note: Full demonstration requires OpenAI API key: {e}")

def demonstrate_enhanced_template_generation():
    """Demonstrate enhanced template generation with thinking features."""
    print("\n📚 Enhanced Template Generation Demo")
    print("=" * 50)
    
    try:
        # Load sample content
        content = load_sample_content()
        print(f"✓ Loaded content ({len(content)} characters)")
        
        # Initialize generator
        generator = TemplateGenerator()
        print("✓ Initialized template generator")
        
        # Analyze content
        analysis = generator.get_content_analysis(content)
        print(f"✓ Content analysis completed:")
        print(f"   - Language: {analysis['language']}")
        print(f"   - Subject Area: {analysis['subject_area']}")
        print(f"   - Is Mathematical: {analysis['is_mathematical']}")
        print(f"   - Math Concepts: {analysis['math_concepts'][:5]}")
        print(f"   - Has Equations: {analysis['has_equations']}")
        print(f"   - Complexity: {analysis['complexity_level']}")
        
        # Set learning goals
        goals = [
            "يحل الطالب المعادلات الخطية خطوة بخطوة",
            "يطبق التفكير المنطقي في حل المسائل الرياضية",
            "يتحقق من صحة الحلول",
            "يربط الرياضيات بالحياة العملية"
        ]
        
        # Generate questions with enhanced thinking
        print("\n✓ Generating questions with mathematical thinking...")
        questions = generator.generate_question_bank(
            content=content,
            goals=goals,
            question_counts={
                "multiple_choice": 3,
                "short_answer": 2,
                "complete": 2,
                "true_false": 2
            },
            difficulty_levels=[1, 2]
        )
        
        print("✓ Questions generated successfully!")
        
        # Display results
        if "_thinking_metadata" in questions:
            thinking_meta = questions["_thinking_metadata"]
            print(f"\n🧠 Thinking Metadata:")
            print(f"   - Enhanced Reasoning: {thinking_meta['enhanced_reasoning']}")
            print(f"   - Math Concepts Used: {thinking_meta['math_concepts'][:3]}")
        
        # Save results
        output_file = "enhanced_math_questions.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print(f"✓ Results saved to {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in template generation: {str(e)}")
        print("Note: This requires OpenAI API key to be set in environment variables")
        return False

def show_key_features():
    """Show the key features of the enhanced system."""
    print("\n🚀 Enhanced Features for Mathematical Content")
    print("=" * 60)
    
    features = [
        "✓ Chain-of-Thought Reasoning: Step-by-step problem solving",
        "✓ Mathematical Tools: Calculator, equation solver, step verification",
        "✓ Smart Content Analysis: Automatic detection of mathematical content",
        "✓ Enhanced Prompting: Specialized prompts for math reasoning",
        "✓ Bilingual Support: Arabic (رياضة) and English mathematics",
        "✓ Difficulty Scaling: Progressive complexity in mathematical problems",
        "✓ Real-world Applications: Connecting math to daily life",
        "✓ Verification System: Automatic checking of mathematical steps",
        "✓ Concept Mapping: Identification and application of math concepts",
        "✓ Error Handling: Graceful handling of mathematical errors"
    ]
    
    for feature in features:
        print(f"  {feature}")

def main():
    """Main demonstration function."""
    print("🧮 Enhanced Educational Template Generation")
    print("🧠 With Mathematical Thinking Features")
    print("🌟 Optimized for Math (رياضة)")
    print("=" * 60)
    
    try:
        # Show features
        show_key_features()
        
        # Demonstrate components
        demonstrate_math_tools()
        demonstrate_chain_of_thought()
        
        # Try enhanced generation
        success = demonstrate_enhanced_template_generation()
        
        if success:
            print("\n🎉 All demonstrations completed successfully!")
        else:
            print("\n⚠️  Some features require OpenAI API key configuration")
        
        print("\n📝 To use the enhanced system:")
        print("   1. Set your OpenAI API key in environment variables")
        print("   2. Run: python main.py questions sample_math_content.txt")
        print("   3. Add --goals for custom learning objectives")
        print("   4. The system will automatically detect mathematical content")
        print("   5. Enhanced reasoning will be applied for math topics")
        
    except Exception as e:
        print(f"❌ Demonstration error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
