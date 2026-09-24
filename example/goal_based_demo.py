#!/usr/bin/env python3
"""
Demo script for Goal-Based Question Generation

This script demonstrates the new goal-based functionality:
1. Scenario A: Goals provided with content
2. Scenario B: No goals - system generates goals first

Usage examples:
python goal_based_demo.py scenario1  # Goals provided
python goal_based_demo.py scenario2  # No goals, system generates them
python goal_based_demo.py both      # Run both scenarios
"""

import sys
import os
import json

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ..generators.template_generator import TemplateGenerator
from ..template.goal_based_template import GoalBasedTemplate

def demo_scenario_1():
    """Scenario 1: Goals provided with content"""
    print("\n" + "="*80)
    print("📋 SCENARIO 1: GOALS PROVIDED WITH CONTENT")
    print("="*80)
    
    # Sample content
    content = """
الرياضيات والهندسة
تعتبر الهندسة فرعاً مهماً من فروع الرياضيات يدرس الأشكال والمساحات والأحجام والمواضع النسبية للأشكال.
تشمل الهندسة المستوية دراسة النقاط والخطوط والزوايا والمضلعات والدوائر.

المثلثات:
المثلث هو شكل هندسي مكون من ثلاث نقاط غير متصلة على خط مستقيم، تسمى رؤوس المثلث، وثلاثة أضلاع.
مجموع زوايا المثلث يساوي 180 درجة دائماً.
أنواع المثلثات:
- المثلث المتساوي الأضلاع: جميع أضلاعه متساوية
- المثلث المتساوي الساقين: ضلعان متساويان
- المثلث مختلف الأضلاع: جميع أضلاعه مختلفة

قانون فيثاغورس:
في المثلث القائم الزاوية: مربع الوتر = مجموع مربعي الضلعين الآخرين
أ² + ب² = ج²
"""
    
    # Provided goals
    goals = [
        "يفهم الطالب المفاهيم الأساسية للهندسة المستوية",
        "يميز الطالب بين أنواع المثلثات المختلفة",
        "يطبق الطالب قانون فيثاغورس في حل المسائل الهندسية",
        "يحسب الطالب مجموع زوايا المثلث ويتحقق من صحته"
    ]
    
    print(f"📖 Content: Mathematical content about geometry and triangles")
    print(f"🎯 Provided Goals: {len(goals)} goals")
    for i, goal in enumerate(goals, 1):
        print(f"   {i}. {goal}")
    
    # Generate goal-based questions
    print(f"\n🔧 Generating goal-based questions...")
    generator = TemplateGenerator()
    
    try:
        result = generator.generate_goal_based_questions(
            content=content,
            goals=goals,
            question_counts={
                "multiple_choice": 6,
                "short_answer": 4,
                "complete": 2,
                "true_false": 2
            }
        )
        
        # Print results using the goal-based template's print method
        goal_template = GoalBasedTemplate()
        goal_template.print_goal_based_result(result)
        
        return result
        
    except Exception as e:
        print(f"❌ Error in Scenario 1: {str(e)}")
        return None

def demo_scenario_2():
    """Scenario 2: No goals provided - system generates them"""
    print("\n" + "="*80)
    print("📋 SCENARIO 2: NO GOALS PROVIDED - SYSTEM GENERATES GOALS")
    print("="*80)
    
    # Sample content - different topic
    content = """
علم الفيزياء - الحركة والقوة
تعتبر الحركة إحدى المفاهيم الأساسية في الفيزياء. الحركة هي تغيير موضع الجسم بمرور الزمن.

أنواع الحركة:
1. الحركة الخطية: حركة الجسم في خط مستقيم
2. الحركة الدائرية: حركة الجسم في مسار دائري
3. الحركة التذبذبية: حركة متكررة ذهاباً وإياباً

قوانين نيوتن للحركة:
القانون الأول: الجسم الساكن يبقى ساكناً والجسم المتحرك يبقى متحركاً ما لم تؤثر عليه قوة خارجية.
القانون الثاني: القوة = الكتلة × التسارع (ق = ك × ت)
القانون الثالث: لكل فعل رد فعل مساوي له في المقدار ومضاد له في الاتجاه.

السرعة والتسارع:
السرعة هي المسافة المقطوعة مقسومة على الزمن المستغرق
التسارع هو معدل تغير السرعة مع الزمن
"""
    
    print(f"📖 Content: Physics content about motion and force")
    print(f"🎯 Goals: None provided - system will generate them automatically")
    
    # Generate goal-based questions without providing goals
    print(f"\n🔧 Generating worksheet with goals first, then questions...")
    generator = TemplateGenerator()
    
    try:
        result = generator.generate_goal_based_questions(
            content=content,
            goals=None,  # No goals provided
            question_counts={
                "multiple_choice": 4,
                "short_answer": 3,
                "complete": 2,
                "true_false": 3
            }
        )
        
        # Print results using the goal-based template's print method
        goal_template = GoalBasedTemplate()
        goal_template.print_goal_based_result(result)
        
        return result
        
    except Exception as e:
        print(f"❌ Error in Scenario 2: {str(e)}")
        return None

def demo_comparison():
    """Compare both scenarios"""
    print("\n" + "="*80)
    print("📊 COMPARISON BETWEEN SCENARIOS")
    print("="*80)
    
    scenario1_result = demo_scenario_1()
    scenario2_result = demo_scenario_2()
    
    if scenario1_result and scenario2_result:
        print(f"\n📈 COMPARISON SUMMARY:")
        
        # Scenario 1 stats
        s1_meta = scenario1_result.get('_goal_based_metadata', {})
        print(f"\n🎯 Scenario 1 (Goals Provided):")
        print(f"   Goals: {s1_meta.get('total_goals', 0)}")
        print(f"   Questions: {s1_meta.get('total_questions', 0)}")
        print(f"   Scenario Type: {s1_meta.get('scenario', 'unknown')}")
        
        # Scenario 2 stats
        s2_meta = scenario2_result.get('_goal_based_metadata', {})
        print(f"\n🎯 Scenario 2 (Goals Generated):")
        print(f"   Goals: {s2_meta.get('total_goals', 0)}")
        print(f"   Questions: {s2_meta.get('total_questions', 0)}")
        print(f"   Scenario Type: {s2_meta.get('scenario', 'unknown')}")
        
        # Show generated worksheet in scenario 2
        if '_generated_worksheet' in scenario2_result:
            worksheet = scenario2_result['_generated_worksheet']
            print(f"\n📄 Generated Worksheet Goals in Scenario 2:")
            for i, goal in enumerate(worksheet.get('goals', []), 1):
                print(f"   {i}. {goal}")

def save_demo_results(scenario1_result, scenario2_result):
    """Save demo results to files for inspection"""
    if scenario1_result:
        with open('demo_scenario1_result.json', 'w', encoding='utf-8') as f:
            json.dump(scenario1_result, f, ensure_ascii=False, indent=2)
        print(f"✅ Scenario 1 results saved to: demo_scenario1_result.json")
    
    if scenario2_result:
        with open('demo_scenario2_result.json', 'w', encoding='utf-8') as f:
            json.dump(scenario2_result, f, ensure_ascii=False, indent=2)
        print(f"✅ Scenario 2 results saved to: demo_scenario2_result.json")

def main():
    """Main demo function"""
    print("🚀 GOAL-BASED QUESTION GENERATION DEMO")
    print("=" * 80)
    print("This demo showcases the new goal-based functionality:")
    print("1. Scenario 1: Goals provided with content")
    print("2. Scenario 2: No goals - system generates goals first")
    
    if len(sys.argv) < 2:
        mode = "both"
    else:
        mode = sys.argv[1].lower()
    
    scenario1_result = None
    scenario2_result = None
    
    try:
        if mode in ["scenario1", "both"]:
            scenario1_result = demo_scenario_1()
        
        if mode in ["scenario2", "both"]:
            scenario2_result = demo_scenario_2()
        
        if mode == "both":
            demo_comparison()
        
        # Save results to files
        if scenario1_result or scenario2_result:
            save_demo_results(scenario1_result, scenario2_result)
        
        print(f"\n✅ Demo completed successfully!")
        print(f"📋 Next steps:")
        print(f"   • Review the generated questions organized by goals")
        print(f"   • Check the goal-question mapping")
        print(f"   • Examine the saved JSON files for detailed results")
        
    except Exception as e:
        print(f"❌ Demo failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
