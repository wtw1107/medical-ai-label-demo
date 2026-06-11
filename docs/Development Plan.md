# Development Plan

## Phase 0: Project Setup
- [ ] Add README
- [ ] Add PRD
- [ ] Add architecture doc
- [ ] Add .gitignore
- [ ] Add .env.example
- [ ] Initialize directory structure

## Phase 1: Backend Foundation
- [ ] Initialize FastAPI backend
- [ ] Add config module
- [ ] Add database setup
- [ ] Add dataset model
- [ ] Add image item model
- [ ] Add upload API

## Phase 2: Frontend Foundation
- [ ] Initialize React frontend
- [ ] Add API client
- [ ] Add upload page
- [ ] Add task creation form

## Phase 3: Label Studio Integration
- [ ] Add Label Studio service
- [ ] Create project via API
- [ ] Import tasks
- [ ] Open Label Studio project URL

## Phase 4: Mock Model Service
- [ ] Add model service
- [ ] Add mock detection endpoint
- [ ] Add mock segmentation endpoint

## Phase 5: Prelabel Flow
- [ ] Add prelabel job
- [ ] Call model service
- [ ] Convert to Label Studio predictions
- [ ] Write predictions to Label Studio
- [ ] Show prelabel status

## Phase 6: Export Flow
- [ ] Fetch annotations
- [ ] Export Label Studio JSON
- [ ] Export simplified JSON
- [ ] Export COCO
- [ ] Export YOLO
- [ ] Export mask PNG
- [ ] Package zip