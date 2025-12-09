"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def serialize_announcement(announcement: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB document to JSON-serializable format"""
    announcement["id"] = str(announcement.pop("_id"))
    return announcement


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_announcements(active_only: bool = Query(True)) -> List[Dict[str, Any]]:
    """
    Get all announcements, optionally filtered to show only active ones
    
    - active_only: If True, return only announcements within their date range
    """
    query = {}
    
    if active_only:
        current_time = datetime.utcnow().isoformat() + "Z"
        query = {
            "$and": [
                {"expiration_date": {"$gte": current_time}},
                {
                    "$or": [
                        {"start_date": {"$exists": False}},
                        {"start_date": None},
                        {"start_date": {"$lte": current_time}}
                    ]
                }
            ]
        }
    
    announcements = list(announcements_collection.find(query).sort("created_at", -1))
    return [serialize_announcement(ann) for ann in announcements]


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """
    Create a new announcement - requires teacher authentication
    
    - message: The announcement text
    - expiration_date: ISO 8601 datetime when announcement expires (required)
    - start_date: ISO 8601 datetime when announcement becomes active (optional)
    - teacher_username: Username of authenticated teacher
    """
    # Validate teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    
    # Validate dates
    try:
        exp_date = datetime.fromisoformat(expiration_date.replace("Z", "+00:00"))
        if exp_date <= datetime.now(exp_date.tzinfo):
            raise HTTPException(status_code=400, detail="Expiration date must be in the future")
        
        if start_date:
            st_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            if st_date >= exp_date:
                raise HTTPException(status_code=400, detail="Start date must be before expiration date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    
    # Create announcement
    announcement = {
        "message": message,
        "start_date": start_date,
        "expiration_date": expiration_date,
        "created_by": teacher_username,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    
    result = announcements_collection.insert_one(announcement)
    announcement["id"] = str(result.inserted_id)
    announcement.pop("_id", None)
    
    return announcement


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """
    Update an existing announcement - requires teacher authentication
    
    - announcement_id: ID of announcement to update
    - message: The updated announcement text
    - expiration_date: Updated ISO 8601 datetime when announcement expires
    - start_date: Updated ISO 8601 datetime when announcement becomes active (optional)
    - teacher_username: Username of authenticated teacher
    """
    # Validate teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    
    # Validate announcement exists
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    existing = announcements_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Validate dates
    try:
        exp_date = datetime.fromisoformat(expiration_date.replace("Z", "+00:00"))
        
        if start_date:
            st_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            if st_date >= exp_date:
                raise HTTPException(status_code=400, detail="Start date must be before expiration date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    
    # Update announcement
    update_data = {
        "message": message,
        "start_date": start_date,
        "expiration_date": expiration_date
    }
    
    result = announcements_collection.update_one(
        {"_id": obj_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0 and result.matched_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update announcement")
    
    # Return updated announcement
    updated = announcements_collection.find_one({"_id": obj_id})
    return serialize_announcement(updated)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...)
) -> Dict[str, str]:
    """
    Delete an announcement - requires teacher authentication
    
    - announcement_id: ID of announcement to delete
    - teacher_username: Username of authenticated teacher
    """
    # Validate teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    
    # Validate announcement exists
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    result = announcements_collection.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}
