Android UI/UX Design Guidelines

This document defines the UI principles for the Android chess coaching application.

The goal is to create a modern, stable, and professional experience.

The application must feel like a serious chess product, not a prototype.

Design Principles

The UI must prioritize:

clarity

stability

responsiveness

minimalism

focus on learning

Theme

The application must use a dark theme by default.

Reasons:

reduced eye strain

modern appearance

common preference among chess players

Visual Style

Recommended characteristics:

deep dark background

high contrast pieces

subtle accent colors

minimal visual clutter

Typography must support hierarchy:

Title
Section header
Body text
Secondary text
Main Screens

The application should include:

Home
Chess Board
Training
Game Review
Deep Chat
Player Profile
Settings
Chess Board Screen

The board is the central UI element.

Features should include:

clear piece rendering

smooth move animations

highlight last move

highlight legal moves

optional hint indicators

Coaching Display

Coaching messages must be easy to read.

Recommended format:

Mistake explanation
↓
Why it matters
↓
Better move suggestion

Short messages are preferred during gameplay.

Deep Chat Screen

Deep chat mode allows extended interaction with the chess coach.

Requirements:

clear message threading

support for long explanations

contextual awareness of current game

The chat should feel similar to modern AI chat interfaces.

Training Screen

Training modules may include:

tactical puzzles

mistake review

recommended exercises

Training should be personalized using analytics.

Player Profile Screen

The profile should visualize learning progress.

Possible sections:

Recent games
Accuracy trend
Common mistakes
Training focus

Charts may include:

accuracy over time

mistake frequency

training effectiveness

Stability Requirements

The app must handle:

slow network

server downtime

partial responses

Graceful fallback is required.

Performance Guidelines

UI must remain smooth:

avoid heavy background tasks

avoid blocking UI thread

cache frequent assets

API_CONTRACTS.md
API Contract Specification

This document defines the REST API contracts between the Android client and backend.

API responses must remain stable and versioned.

API Principles

All endpoints must:

validate input

return structured JSON

provide consistent error responses

log events via SECA Events

Authentication

Authenticated endpoints require:

Authorization: Bearer <token>

Auth validation occurs via SECA Auth.

Endpoint: Engine Evaluation
POST /engine/eval

Purpose:

Evaluate a position.

Request
{
 "fen": "string",
 "depth": number
}
Response
{
 "best_move": "string",
 "evaluation": number,
 "source": "engine | cache",
 "analysis_depth": number
}
Endpoint: Coaching
POST /coach

Purpose:

Generate coaching feedback.

Request
{
 "fen": "string",
 "played_move": "string"
}
Response
{
 "mistake": "string",
 "consequence": "string",
 "better_move": "string",
 "category": "string",
 "severity": "string"
}
Endpoint: Game Finish
POST /game/finish

Purpose:

Record completed game and update analytics.

Request
{
 "game_id": "string",
 "moves": ["string"],
 "result": "win | loss | draw"
}
Response
{
 "status": "recorded"
}
Endpoint: Next Training
GET /next-training

Purpose:

Provide training recommendation.

Response
{
 "training_type": "string",
 "reason": "string",
 "priority": "low | medium | high"
}
Endpoint: Deep Chat
POST /chat

Purpose:

Deep conversational chess interaction.

Request
{
 "message": "string",
 "game_context": {},
 "player_profile": {}
}
Response
{
 "response": "string",
 "topic": "opening | tactics | strategy | endgame",
 "confidence": 0-1
}
Error Response Format

All errors must follow a standard structure.

{
 "error": "error_code",
 "message": "description"
}
API Versioning

Future changes should use versioning.

Example:

/api/v1/coach
/api/v2/coach
