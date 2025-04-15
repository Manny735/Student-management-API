from fastapi import FastAPI, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel, EmailStr
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables and set up Supabase
load_dotenv()
app = FastAPI(title="Student Management System API")

def get_supabase() -> Client:
    return create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_KEY")
    )

# Simple data models
class StudentBase(BaseModel):
    name: str
    email: EmailStr

class Student(StudentBase):
    id: int

class CourseBase(BaseModel):
    name: str
    instructor: str
    prerequisites: Optional[List[str]] = []

class Course(CourseBase):
    id: int

class EnrollmentBase(BaseModel):
    student_id: int
    course_id: int
    grade: Optional[float] = None

class Enrollment(EnrollmentBase):
    pass

# Student endpoints
@app.post("/students/", response_model=Student)
async def create_student(student: StudentBase, supabase: Client = Depends(get_supabase)):
    # Check for duplicate email
    existing = supabase.table("students").select("*").eq("email", student.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create student
    result = supabase.table("students").insert(student.dict()).execute()
    return result.data[0]

@app.get("/students/", response_model=List[Student])
async def get_students(supabase: Client = Depends(get_supabase)):
    result = supabase.table("students").select("*").execute()
    return result.data


@app.delete("/students/{student_id}")
async def delete_student(student_id: int, supabase: Client = Depends(get_supabase)):
    # Delete related enrollments first
    supabase.table("enrollments").delete().eq("student_id", student_id).execute()
    
    # Delete student
    supabase.table("students").delete().eq("id", student_id).execute()
    return {"message": "Student deleted"}

# Course endpoints
@app.post("/courses/", response_model=Course)
async def create_course(course: CourseBase, supabase: Client = Depends(get_supabase)):
    result = supabase.table("courses").insert(course.dict()).execute()
    return result.data[0]

@app.get("/courses/", response_model=List[Course])
async def get_courses(supabase: Client = Depends(get_supabase)):
    result = supabase.table("courses").select("*").execute()
    return result.data

@app.delete("/courses/{course_id}")
async def delete_course(course_id: int, supabase: Client = Depends(get_supabase)):
    # Delete related enrollments first
    supabase.table("enrollments").delete().eq("course_id", course_id).execute()
    
    # Delete course
    supabase.table("courses").delete().eq("id", course_id).execute()
    return {"message": "Course deleted"}

# Enrollment endpoints
@app.post("/enrollments/", response_model=Enrollment)
async def create_enrollment(enrollment: EnrollmentBase, supabase: Client = Depends(get_supabase)):
    # Check if student and course exist
    student = supabase.table("students").select("*").eq("id", enrollment.student_id).execute()
    course = supabase.table("courses").select("*").eq("id", enrollment.course_id).execute()
    
    if not student.data:
        raise HTTPException(status_code=404, detail="Student not found")
    if not course.data:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Check for duplicate enrollment
    existing = supabase.table("enrollments").select("*")\
        .eq("student_id", enrollment.student_id)\
        .eq("course_id", enrollment.course_id).execute()
    
    if existing.data:
        raise HTTPException(status_code=400, detail="Student already enrolled in this course")
    
    # Create enrollment
    result = supabase.table("enrollments").insert(enrollment.dict()).execute()
    return result.data[0]

@app.get("/enrollments/", response_model=List[Enrollment])
async def get_enrollments(
    student_id: Optional[int] = None, 
    course_id: Optional[int] = None,
    supabase: Client = Depends(get_supabase)
):
    query = supabase.table("enrollments").select("*")
    
    if student_id:
        query = query.eq("student_id", student_id)
    if course_id:
        query = query.eq("course_id", course_id)
        
    result = query.execute()
    return result.data

@app.put("/enrollments/")
async def update_grade(
    student_id: int, 
    course_id: int, 
    grade: float,
    supabase: Client = Depends(get_supabase)
):
    # Check if enrollment exists
    existing = supabase.table("enrollments").select("*")\
        .eq("student_id", student_id)\
        .eq("course_id", course_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    # Update grade
    result = supabase.table("enrollments").update({"grade": grade})\
        .eq("student_id", student_id)\
        .eq("course_id", course_id).execute()
    
    return result.data[0]

@app.delete("/enrollments/")
async def delete_enrollment(
    student_id: int, 
    course_id: int,
    supabase: Client = Depends(get_supabase)
):
    # Delete enrollment
    supabase.table("enrollments").delete()\
        .eq("student_id", student_id)\
        .eq("course_id", course_id).execute()
    
    return {"message": "Enrollment deleted"}

# Calculate GPA
@app.get("/students/{student_id}/gpa")
async def calculate_gpa(student_id: int, supabase: Client = Depends(get_supabase)):
    enrollments = supabase.table("enrollments").select("*")\
        .eq("student_id", student_id)\
        .not_.is_("grade", None).execute()  # ← THIS works

    if not enrollments.data:
        return {"gpa": 0.0, "message": "No grades found"}

    total_points = sum(enrollment['grade'] for enrollment in enrollments.data)
    gpa = total_points / len(enrollments.data)

    return {"gpa": round(gpa, 2)}


# Entry point for running in Jupyter notebook
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
