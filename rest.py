from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .service import TeamManagementService

app = FastAPI()
service = TeamManagementService()

class TeamCreate(BaseModel):
    team_name: str

class TeamMember(BaseModel):
    username: str
    team_name: str

class ChatTeam(BaseModel):
    chat_id: int
    team_name: str

@app.post("/teams")
async def create_team(team: TeamCreate):
    result = service.create_team(team.team_name)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.post("/teams/members")
async def add_team_member(member: TeamMember):
    result = service.add_member_to_team(member.username, member.team_name)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.delete("/teams/members")
async def remove_team_member(member: TeamMember):
    result = service.remove_member_from_team(member.username, member.team_name)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.post("/chats/teams")
async def add_team_to_chat(chat_team: ChatTeam):
    result = service.add_team_to_chat(chat_team.chat_id, chat_team.team_name)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.delete("/users/{username}")
async def offboard_user(username: str):
    result = service.offboard_user(username)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# Usage example
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
