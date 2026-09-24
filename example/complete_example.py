"""
Complete Template Generation Example

This script demonstrates how to use all available templates including the new mind map functionality.
"""

import json
from ..generators.template_generator import TemplateGenerator

def comprehensive_example():
    """Generate all template types for the same content."""
    
    # Sample educational content
    sample_content = """
    الذكاء الاصطناعي في التعليم

    الذكاء الاصطناعي (AI) يُحدث ثورة في مجال التعليم من خلال توفير حلول مبتكرة لتحسين عملية التعلم والتعليم.

    التطبيقات الرئيسية:
    1. التعلم المخصص - تخصيص المحتوى حسب احتياجات كل طالب
    2. التقييم الآلي - تصحيح الامتحانات وتوفير تغذية راجعة فورية
    3. المساعدة الذكية - روبوتات المحادثة للإجابة على أسئلة الطلاب
    4. تحليل البيانات التعليمية - فهم أنماط التعلم وتحسين المناهج

    الفوائد:
    - تحسين جودة التعليم
    - زيادة الكفاءة في العملية التعليمية
    - توفير الوقت للمعلمين
    - دعم التعلم المستمر

    التحديات:
    - الحاجة إلى التدريب التقني
    - القضايا الأخلاقية والخصوصية
    - التكلفة العالية للتنفيذ
    - مقاومة التغيير من بعض المعلمين
    """
    
    # Learning goals for goal-based templates
    learning_goals = [
        "فهم الطلاب لمفهوم الذكاء الاصطناعي في التعليم",
        "تحديد التطبيقات الرئيسية للذكاء الاصطناعي في التعليم",
        "تقييم فوائد وتحديات استخدام الذكاء الاصطناعي في التعليم",
        "تطبيق المعرفة حول الذكاء الاصطناعي في سياقات تعليمية مختلفة"
    ]
    
    print("🚀 Comprehensive Template Generation Example")
    print("=" * 60)
    
    # Initialize generator
    generator = TemplateGenerator()
    
    results = {}
    
    try:
        # 1. Generate Questions
        print("\n📝 1. Generating Question Bank...")
        questions = generator.generate_question_bank(
            content=sample_content,
            goals=learning_goals,
            question_counts={
                "multiple_choice": 4,
                "short_answer": 3,
                "complete": 2,
                "true_false": 3
            }
        )
        results["questions"] = questions
        print(f"   ✅ Generated {sum(len(v) for k, v in questions.items() if isinstance(v, list))} questions")
        
        # 2. Generate Goal-Based Questions
        print("\n🎯 2. Generating Goal-Based Questions...")
        goal_based_questions = generator.generate_goal_based_questions(
            content=sample_content,
            goals=learning_goals,
            question_counts={
                "multiple_choice": 6,
                "short_answer": 4,
                "complete": 2,
                "true_false": 2
            }
        )
        results["goal_based_questions"] = goal_based_questions
        print(f"   ✅ Generated {goal_based_questions.get('_goal_based_metadata', {}).get('total_questions', 0)} questions for {len(goal_based_questions.get('learning_goals', []))} goals")
        
        # 3. Generate Worksheet
        print("\n📋 3. Generating Worksheet...")
        worksheet = generator.generate_worksheet(
            content=sample_content,
            goals=learning_goals
        )
        results["worksheet"] = worksheet
        print(f"   ✅ Generated worksheet with {len(worksheet.get('goals', []))} goals and {len(worksheet.get('applications', []))} applications")
        
        # 4. Generate Summary
        print("\n📄 4. Generating Summary...")
        summary = generator.generate_summary(content=sample_content)
        results["summary"] = summary
        print("   ✅ Generated summary with opening, main content, and conclusion")
        
        # 5. Generate Mind Map (NEW!)
        print("\n🧠 5. Generating Mind Map...")
        mindmap = generator.generate_mindmap(content=sample_content)
        results["mindmap"] = mindmap
        print(f"   ✅ Generated mind map with {len(mindmap.get('nodeDataArray', []))} nodes")
        
        # Print detailed results
        print("\n" + "=" * 60)
        print("📊 DETAILED RESULTS")
        print("=" * 60)
        
        # Questions summary
        print("\n📝 QUESTION BANK:")
        for q_type, questions_list in questions.items():
            if isinstance(questions_list, list) and questions_list:
                print(f"   {q_type.replace('_', ' ').title()}: {len(questions_list)} questions")
        
        # Goal-based questions summary
        print("\n🎯 GOAL-BASED QUESTIONS:")
        goal_mappings = goal_based_questions.get('goal_question_mapping', [])
        for mapping in goal_mappings:
            print(f"   • {mapping.get('goal_text', '')[:50]}...")
            print(f"     Questions: {mapping.get('question_count', 0)} total")
        
        # Worksheet summary
        print("\n📋 WORKSHEET:")
        print(f"   Goals: {len(worksheet.get('goals', []))}")
        print(f"   Applications: {len(worksheet.get('applications', []))}")
        print(f"   Vocabulary Terms: {len(worksheet.get('vocabulary', []))}")
        
        # Summary preview
        print("\n📄 SUMMARY:")
        summary_text = summary.get('summary', '')
        print(f"   Content: {summary_text[:100]}..." if len(summary_text) > 100 else f"   Content: {summary_text}")
        
        # Mind map summary
        print("\n🧠 MIND MAP:")
        nodes = mindmap.get('nodeDataArray', [])
        print(f"   Total Nodes: {len(nodes)}")
        if nodes:
            root = next((n for n in nodes if n.get('parent') is None), {})
            print(f"   Root Topic: {root.get('text', 'N/A')}")
            main_branches = [n for n in nodes if n.get('parent') == root.get('key', 0)]
            print(f"   Main Branches: {len(main_branches)}")
        
        # Save all results
        print("\n💾 SAVING RESULTS:")
        for template_type, result in results.items():
            filename = f"example_{template_type}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"   ✅ {template_type.title()}: {filename}")
        
        print("\n🎉 All templates generated successfully!")
        print("\nTemplate Types Available:")
        for i, template_type in enumerate(generator.get_supported_templates(), 1):
            print(f"   {i}. {template_type}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise

def demonstrate_mind_map_integration():
    """Demonstrate how the mind map integrates with the existing system."""
    
    print("\n" + "=" * 60)
    print("🗺️ MIND MAP INTEGRATION DEMONSTRATION")
    print("=" * 60)
    
    generator = TemplateGenerator()
    
    # Show that mind map follows the same pattern as other templates
    print("\n1. Using the general template method:")
    mindmap1 = generator.generate_template(
        template_type="mindmap",
        content="Sample content for mind map generation"
    )
    print(f"   ✅ Generated via generate_template(): {len(mindmap1.get('nodeDataArray', []))} nodes")
    
    print("\n2. Using the specific convenience method:")
    mindmap2 = generator.generate_mindmap(
        content="Sample content for mind map generation"
    )
    print(f"   ✅ Generated via generate_mindmap(): {len(mindmap2.get('nodeDataArray', []))} nodes")
    
    print("\n3. Mind map structure follows GoJS format:")
    print(f"   Class: {mindmap1.get('class', 'N/A')}")
    print(f"   Has nodeDataArray: {'nodeDataArray' in mindmap1}")
    print(f"   Compatible with GoJS: ✅")
    
    print("\n4. Includes same metadata as other templates:")
    metadata = mindmap1.get('_metadata', {})
    print(f"   Language detected: {metadata.get('language', 'N/A')}")
    print(f"   Content analysis: {'content_analysis' in metadata}")
    print(f"   Generation params: {'generation_params' in metadata}")

if __name__ == "__main__":
    try:
        # Run comprehensive example
        results = comprehensive_example()
        
        # Demonstrate integration
        demonstrate_mind_map_integration()
        
        print("\n✨ Mind map successfully integrated into the template generation system!")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
