import os
import sys
import json
import argparse
from typing import Dict, Any

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from generators.template_generator import TemplateGenerator
from config.settings import Settings

def load_content_from_file(file_path: str) -> str:
    """Load content from a text file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Content file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error reading content file: {str(e)}")

def save_result_to_file(result: Dict[str, Any], output_path: str):
    """Save the generated result to a JSON file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ Result saved to: {output_path}")
    except Exception as e:
        print(f"❌ Error saving result: {str(e)}")

def print_result(result: Dict[str, Any], template_type: str):
    """Print the generated result in a formatted way."""
    print(f"\n🎯 Generated {template_type.upper()} Template")
    print("=" * 50)
    
    if template_type == "questions":
        print_question_bank(result)
    elif template_type == "goal_based_questions":
        print_goal_based_questions(result)
    elif template_type == "worksheet":
        print_worksheet(result)
    elif template_type == "summary":
        print_summary(result)
    elif template_type == "mindmap":
        print_mindmap(result)
    
    # Print metadata if available
    if "_metadata" in result:
        metadata = result["_metadata"]
        print(f"\n📊 Metadata:")
        print(f"   Language: {metadata.get('language', 'Unknown')}")
        
        content_analysis = metadata.get('content_analysis', {})
        if content_analysis:
            print(f"   Subject Area: {content_analysis.get('subject_area', 'Unknown')}")
            print(f"   Mathematical Content: {content_analysis.get('is_mathematical', False)}")
            if content_analysis.get('math_concepts'):
                print(f"   Math Concepts: {', '.join(content_analysis['math_concepts'][:5])}")
            print(f"   Complexity: {content_analysis.get('complexity_level', 'Unknown')}")
    
    # Print thinking metadata if available
    if "_thinking_metadata" in result:
        thinking_meta = result["_thinking_metadata"]
        print(f"\n🧠 Thinking Enhancement:")
        print(f"   Enhanced Reasoning: {thinking_meta.get('enhanced_reasoning', False)}")
        print(f"   Mathematical Focus: {thinking_meta.get('is_mathematical', False)}")
        if thinking_meta.get('math_concepts'):
            print(f"   Applied Concepts: {', '.join(thinking_meta['math_concepts'][:3])}")
    
    # Print goal-based metadata if available
    if "_goal_based_metadata" in result:
        goal_meta = result["_goal_based_metadata"]
        print(f"\n🎯 Goal-Based Generation:")
        print(f"   Total Goals: {goal_meta.get('total_goals', 0)}")
        print(f"   Total Questions: {goal_meta.get('total_questions', 0)}")
        print(f"   Scenario: {goal_meta.get('scenario', 'unknown')}")
        print(f"   Questions per Goal: {goal_meta.get('questions_per_goal_distribution', {})}")

def print_goal_based_questions(result: Dict[str, Any]):
    """Print goal-based question bank in a formatted way."""
    # Print goals
    goals = result.get('learning_goals', [])
    print(f"\n🎯 LEARNING GOALS ({len(goals)}):")
    for i, goal in enumerate(goals, 1):
        print(f"   {i}. [{goal['id']}] {goal['text']}")
        print(f"      Priority: {goal['priority']}, Cognitive Level: {goal['cognitive_level']}")
    
    # Print goal-question mapping
    mappings = result.get('goal_question_mapping', [])
    print(f"\n📋 GOAL-QUESTION MAPPING:")
    for mapping in mappings:
        print(f"   🎯 {mapping['goal_text'][:60]}...")
        print(f"      Questions: {mapping['question_count']} total")
        question_types = mapping['question_types']
        print(f"      Types: MC({question_types.get('multiple_choice', 0)}), "
              f"SA({question_types.get('short_answer', 0)}), "
              f"Comp({question_types.get('complete', 0)}), "
              f"TF({question_types.get('true_false', 0)})")
        print()
    
    # Print sample questions by goal
    questions_by_goal = result.get('questions_by_goal', {})
    if questions_by_goal:
        print(f"\n📝 QUESTIONS BY GOAL:")
        for goal_id, goal_questions in questions_by_goal.items():
            goal_info = next((g for g in goals if g['id'] == goal_id), {})
            print(f"\n   🎯 {goal_info.get('text', goal_id)}")
            
            for question_type, questions in goal_questions.items():
                if questions:
                    print(f"      📋 {question_type.replace('_', ' ').title()}:")
                    for i, q in enumerate(questions[:2], 1):  # Show first 2 questions
                        print(f"         {i}. {q.get('question', '')[:80]}...")
                        if 'choices' in q:
                            for j, choice in enumerate(q['choices'][:2]):  # Show first 2 choices
                                marker = "✓" if j == q.get('answer_key', -1) else " "
                                print(f"            {chr(65+j)}. {choice[:40]}... {marker}")
                    if len(questions) > 2:
                        print(f"         ... and {len(questions) - 2} more")
        
        # Also print traditional structure for backward compatibility
        print(f"\n📝 ALL QUESTIONS (Traditional Structure):")
        print_question_bank(result)

def print_question_bank(result: Dict[str, Any]):
    """Print question bank in a formatted way."""
    for question_type, questions in result.items():
        if question_type.startswith("_"):  # Skip metadata
            continue
            
        # Skip goal-based fields in traditional question banks
        if question_type in ["learning_goals", "goal_question_mapping", "questions_by_goal"]:
            continue
            
        if questions:
            print(f"\n📝 {question_type.replace('_', ' ').title()}:")
            for i, q in enumerate(questions, 1):
                print(f"   {i}. {q.get('question', '')}")
                if 'choices' in q:
                    for j, choice in enumerate(q['choices']):
                        marker = "✓" if j == q.get('answer_key', -1) else " "
                        print(f"      {chr(65+j)}. {choice} {marker}")
                elif 'answer' in q:
                    print(f"      Answer: {q['answer']}")
                print()

def print_worksheet(result: Dict[str, Any]):
    """Print worksheet in a formatted way."""
    if 'goals' in result:
        print(f"\n🎯 Goals:")
        for goal in result['goals']:
            print(f"   • {goal}")
    
    if 'applications' in result:
        print(f"\n🔧 Applications:")
        for app in result['applications']:
            print(f"   • {app}")
    
    if 'vocabulary' in result:
        print(f"\n📚 Vocabulary:")
        for vocab in result['vocabulary']:
            print(f"   • {vocab.get('term', '')}: {vocab.get('definition', '')}")
    
    if 'teacher_guidelines' in result:
        print(f"\n👨‍🏫 Teacher Guidelines:")
        for guideline in result['teacher_guidelines']:
            print(f"   • {guideline}")

def print_summary(result: Dict[str, Any]):
    """Print summary in a formatted way."""
    print(f"\n🚀 Opening: {result.get('opening', '')}")
    print(f"\n📋 Summary: {result.get('summary', '')}")
    print(f"\n🎬 Ending: {result.get('ending', '')}")

def print_mindmap(result: Dict[str, Any]):
    """Print mind map in a formatted way."""
    print(f"\n🧠 Mind Map Structure:")
    print(f"   Model Class: {result.get('class', 'go.TreeModel')}")
    
    nodes = result.get('nodeDataArray', [])
    print(f"   Total Nodes: {len(nodes)}")
    
    if nodes:
        # Find root node
        root_node = next((node for node in nodes if node.get('parent') is None), None)
        if root_node:
            print(f"   Root Topic: {root_node.get('text', 'N/A')}")
        
        # Find main branches (direct children of root)
        root_key = root_node.get('key', 0) if root_node else 0
        main_branches = [node for node in nodes if node.get('parent') == root_key]
        
        print(f"   Main Branches: {len(main_branches)}")
        for i, branch in enumerate(main_branches, 1):
            print(f"     {i}. {branch.get('text', 'N/A')} ({branch.get('brush', 'default color')})")
            
            # Find sub-branches
            branch_key = branch.get('key')
            sub_branches = [node for node in nodes if node.get('parent') == branch_key]
            if sub_branches:
                print(f"        └─ {len(sub_branches)} sub-topics")
                for sub in sub_branches[:2]:  # Show first 2 sub-topics
                    print(f"           • {sub.get('text', 'N/A')}")
                if len(sub_branches) > 2:
                    print(f"           • ... and {len(sub_branches) - 2} more")
    
    print(f"\n💡 Mind map is ready for GoJS visualization!")
    print(f"   Use the nodeDataArray to render the mind map in your application.")

def main():
    """Main function to run the template generator."""
    parser = argparse.ArgumentParser(description="Educational Template Generator")
    
    parser.add_argument("template_type", choices=["questions", "worksheet", "summary", "goal_based_questions", "mindmap"],
                       help="Type of template to generate")
    parser.add_argument("content_file", help="Path to the content file")
    parser.add_argument("--goals", nargs="+", help="Learning goals")
    parser.add_argument("--output", "-o", help="Output file path (JSON)")
    parser.add_argument("--mc", type=int, default=3, help="Number of multiple choice questions")
    parser.add_argument("--sa", type=int, default=2, help="Number of short answer questions")
    parser.add_argument("--comp", type=int, default=2, help="Number of completion questions")
    parser.add_argument("--tf", type=int, default=2, help="Number of true/false questions")
    parser.add_argument("--difficulty", nargs="+", type=int, choices=[1, 2, 3], 
                       default=[1, 2, 3], help="Difficulty levels to include")
    parser.add_argument("--thinking", action="store_true", 
                       help="Enable enhanced thinking features for mathematical content")
    parser.add_argument("--demo", action="store_true",
                       help="Run enhanced mathematical reasoning demo")
    
    args = parser.parse_args()
    
    # Handle demo mode
    if args.demo:
        print("🚀 Running Enhanced Mathematical Reasoning Demo...")
        try:
            from enhanced_math_demo import main as demo_main
            return demo_main()
        except ImportError as e:
            print(f"❌ Demo not available: {e}")
            return 1
    
    try:
        # Load content
        print(f"📖 Loading content from: {args.content_file}")
        content = load_content_from_file(args.content_file)
        
        # Initialize generator
        print("🔧 Initializing template generator...")
        generator = TemplateGenerator()
        
        # Prepare parameters
        kwargs = {}
        if args.template_type in ["questions", "goal_based_questions"]:
            kwargs = {
                "question_counts": {
                    "multiple_choice": args.mc,
                    "short_answer": args.sa,
                    "complete": args.comp,
                    "true_false": args.tf
                },
                "difficulty_levels": args.difficulty
            }
        
        # Generate template
        print(f"🎨 Generating {args.template_type} template...")
        result = generator.generate_template(
            template_type=args.template_type,
            content=content,
            goals=args.goals,
            **kwargs
        )
        
        # Display result
        print_result(result, args.template_type)
        
        # Save to file if requested
        if args.output:
            save_result_to_file(result, args.output)
        
        print("\n✅ Template generation completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
