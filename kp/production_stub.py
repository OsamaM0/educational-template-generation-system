"""Deterministic placeholders for exercising the generalized contract only."""

def block(kind, **values):
    return dict(kind=kind,title=None,text=None,items=None,columns=None,rows=None,
                question_ref=None,teacher_only=False) | values


def complete(step, meta):
    en = meta['language'] == 'en'
    mark = '[Test placeholder] ' if en else '[نص تجريبي] '
    if step == 'topics':
        return {'topics':[{
            'goal_id':g['id'], 'product_type':('Explanatory resource' if en else 'مورد تفسيري'),
            'title':mark + (f'Resource {n}' if en else f'المورد {n}'),
            'subtitle':('Lesson reference' if en else 'مرجع للدرس'),
            'purpose':('Explain the lesson goal.' if en else 'توضيح الهدف التعليمي.'),
            'audience':('Learners' if en else 'المتعلمون'),
            'lesson_connection':('A reference addressing the worksheet goal.' if en else 'مرجع مرتبط بهدف ورقة العمل.'),
            'concepts':(['Lesson concept'] if en else [g['text']]),
            'layout':'document','question_refs':[]
        } for n,g in enumerate(meta['goals'],1)]}
    if step == 'project':
        return {'sections':[{'id':'explanation','title':('Explanation' if en else 'التفسير'),
                             'role':'explanation', 'blocks':[block('paragraph',text=mark +
                              ('Replace this placeholder with actual lesson knowledge.' if en else 'يستبدل هذا النص بمحتوى معرفي حقيقي من الدرس.'))]}]}
    return {'questions':[{'question_ref':q['id'],'question_text':q['text'],
                           'choices':q.get('choices'),'answer_text':q['answer'],
                           'explanation':mark + ('Explanation' if en else 'تفسير')}
                          for q in meta['questions']]}
