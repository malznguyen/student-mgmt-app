# Data Model (baseline)

Collections:
- students: {_id, full_name, email, major_dept_id, year, phone?}
- instructors: {_id, full_name, email, dept_id, title?}
- departments: {_id, name, office?, phone?}
- courses: {_id, title, credits, dept_id, prereq_ids[]?}
- class_sections: {_id, course_id, semester, section_no, instructor_id, capacity?, room?, schedule[]}
- enrollments: {_id?, student_id, section_id, semester, midterm?, final?, bonus?, letter?}

Relations:
- courses.dept_id -> departments._id
- class_sections.course_id -> courses._id
- class_sections.instructor_id -> instructors._id
- enrollments.section_id -> class_sections._id
- enrollments.student_id -> students._id
