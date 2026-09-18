#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

#====================================================================================================
# Testing Data - Current Task
#====================================================================================================
## user_problem_statement: Understand the complete Shree-Stay-Homes-PG-Invoice-generater repository, run it locally, show a preview, and preserve code/logic while keeping Git actions permission-gated.
## backend:
##   - task: "Local backend startup and repository baseline"
##     implemented: true
##     working: true
##     file: "backend/server.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##         -working: "NA"
##         -agent: "main"
##         -comment: "Backend is running under supervisor on 0.0.0.0:8001. No source changes were made. Existing test reports record 24/24 backend tests passing; verify current health and baseline endpoints."
##         -working: true
##         -agent: "testing"
##         -comment: "Backend baseline verification complete. Supervisor status: RUNNING (pid 1343, uptime 0:12:20). Hermetic test suite: 24/24 tests PASSED in 7.59s using temporary database (no live data touched). Live API verification: 10/10 endpoints PASSED including GET /api/ (health), /settings, /invoices/next-number, /dashboard/stats, and all list endpoints. Live database initialized and empty (0 invoices, 0 tenants). All baseline functionality working correctly."
## frontend:
##   - task: "Local frontend startup and preview"
##     implemented: true
##     working: true
##     file: "frontend/src/App.js"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##         -working: "NA"
##         -agent: "main"
##         -comment: "Frontend dependencies were restored from the pinned lockfile after a non-source Yarn cache failure. Frontend is running under supervisor on 0.0.0.0:3000; preview/browser verification is still pending."
##         -working: "NA"
##         -agent: "user"
##         -comment: "User explicitly requested a working preview without changing application code or logic; browser verification is approved."
##         -working: true
##         -agent: "testing"
##         -comment: "Frontend preview fully functional. Comprehensive UI testing completed (1920x800 viewport): ✅ Root URL (/) correctly redirects to /dashboard. ✅ Dashboard renders with proper branding 'SHREE STAY HOMES & PG' and subtitle. ✅ All 14 navigation items present and accessible. ✅ All 13 routes tested successfully (Create Invoice, History, Tenants, Settings, Backup, Monthly Billing, Food Orders, Expenses, Reports, Import Google Forms, Rooms & Beds, Payments, Overdue). ✅ No backend offline banner (backend is reachable). ✅ No network failures detected. ✅ No page errors or broken routes. Minor: 4 console warnings about chart dimensions (recharts library with empty data - cosmetic only, does not affect functionality). Dashboard shows proper empty state with metrics at ₹0.00 and 'No invoices yet' message. Screenshot captured. All core functionality working correctly."
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 9
##   run_ui: true
## test_plan:
##   current_focus:
##     - "Frontend preview verification complete"
##   stuck_tasks: []
##   test_all: false
##   test_priority: "high_first"
## agent_communication:
##     -agent: "main"
##     -message: "Repository README, PRD, backend/frontend entry points, package manifests, and service configuration were reviewed. Only dependency environment/cache setup was touched; application source and lockfiles remain unchanged."
##     -agent: "testing"
##     -message: "Backend baseline testing completed successfully. All 24 hermetic tests passed (using temporary DB, no live data touched). All 10 live API endpoints verified working. Live database initialized correctly with 0 records. Backend is fully operational and ready for use. Frontend testing was not performed as per instructions (UI testing requires user approval)."
##     -agent: "testing"
##     -message: "Frontend UI testing completed successfully. Non-destructive verification performed at http://localhost:3000 with 1920x800 viewport. All navigation routes working (13/13 tested). Dashboard renders correctly with branding, metrics, and empty state. Backend integration confirmed (no offline banner). Only minor console warnings from chart library with empty data (cosmetic, non-blocking). Application is fully functional and ready for use. No code changes were made during testing."
