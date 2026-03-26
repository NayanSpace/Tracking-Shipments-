# Multi-Carrier Shipment Tracking System - Implementation Plan

## Project Overview

Build a multi-user shipment tracking web application that scrapes real-time data from **UPS, FedEx, Day & Ross, and Polaris Transportation**. Users can submit multiple tracking numbers, view live status updates with auto-refresh every 3 hours, and tracking data auto-deletes 3 days post-delivery. Deploy on Render free tier using **Python FastAPI + Playwright + PostgreSQL** with JWT authentication.

---

## Table of Contents

1. [Requirements Summary](#requirements-summary)
2. [Technology Stack](#technology-stack)
3. [Carrier Research](#carrier-research)
4. [Implementation Steps](#implementation-steps)
   - [Phase 1: Project Setup & Environment Configuration](#phase-1-project-setup--environment-configuration)
   - [Phase 2: Database Design & Setup](#phase-2-database-design--setup)
   - [Phase 3: Authentication System](#phase-3-authentication-system) _(includes admin dependency)_
   - [Phase 4: Web Scraping Implementation](#phase-4-web-scraping-implementation)
   - [Phase 5: Tracking API Endpoints](#phase-5-tracking-api-endpoints)
   - [Phase 6: Background Job Scheduler](#phase-6-background-job-scheduler) _(includes Render sleep mitigation)_
   - [Phase 7: Frontend Development](#phase-7-frontend-development) _(includes App.jsx routing + auth.js)_
   - [Phase 8: Error Handling & User Experience](#phase-8-error-handling--user-experience)
   - [Phase 9: Deployment Configuration](#phase-9-deployment-configuration) _(includes health check + full render.yaml)_
   - [Phase 10: Testing & Optimization](#phase-10-testing--optimization)
5. [File Structure](#file-structure)
6. [Verification Steps](#verification-steps)
7. [Decisions & Assumptions](#decisions--assumptions)
8. [Further Considerations](#further-considerations)
9. [Timeline Estimate](#timeline-estimate)

---

## Requirements Summary

### Core Features

- **Multi-carrier support**: UPS, FedEx, Day & Ross, Polaris Transportation
- **Multi-user authentication**: Secure account creation and login
- **Bulk tracking**: Enter multiple tracking numbers at once
- **Real-time scraping**: Fetch current status from carrier websites
- **Auto-refresh**: Update undelivered shipments every 3 hours
- **Auto-cleanup**: Remove tracking data 3 days after delivery
- **Manual refresh**: On-demand update button
- **Professional UI**: Clean, work-environment appropriate design

### Technical Requirements

- **No carrier APIs**: Scrape data directly from websites
- **Deployment**: Render free tier (512MB RAM, 15-min sleep after inactivity)
- **Database**: PostgreSQL (free tier: 1GB storage)
- **Security**: Multi-user isolation, JWT authentication, rate limiting
- **Performance**: Fast page loads (<2s), efficient scraping

---

## Technology Stack

### Backend

- **FastAPI** (Python web framework)
  - Fast, async support
  - Auto-generated API documentation
  - Excellent Pydantic validation
  - Small memory footprint for Render free tier

- **Playwright** (Web scraping)
  - Modern browser automation
  - Better stealth mode than Selenium
  - Handles JavaScript-heavy pages
  - Built-in waiting mechanisms

- **SQLAlchemy** (ORM)
  - Async support
  - PostgreSQL compatibility
  - Prevents SQL injection

- **APScheduler** (Background jobs)
  - Auto-refresh every 3 hours
  - Daily cleanup job

- **JWT + Bcrypt** (Authentication)
  - Stateless tokens (no session storage needed)
  - Industry-standard password hashing

### Frontend

- **React** (UI framework)
  - Large ecosystem
  - Good Tailwind CSS integration
  - Excellent developer experience

- **Vite** (Build tool)
  - Fast development server
  - Optimized production builds

- **Tailwind CSS** (Styling)
  - Rapid UI development
  - Responsive design utilities
  - Professional appearance

- **Axios** (HTTP client)
  - Easy JWT token management
  - Request/response interceptors

### Database

- **PostgreSQL**
  - Better for multi-user systems
  - Render free tier available
  - JSONB support for raw scraping data

### Deployment

- **Render** (Hosting platform)
  - Free tier: 512MB RAM, sleeps after 15min inactivity
  - Docker support
  - Auto-deploys from Git
  - HTTPS included

---

## Carrier Research

### 1. UPS (ups.com)

- **Tracking URL**: `https://www.ups.com/track?tracknum={tracking_number}`
- **Challenge**: Heavy JavaScript rendering required
- **Anti-bot Protection**: Moderate - uses Cloudflare but allows headless browsers with proper headers
- **Data Location**: JSON response from API endpoint after page load
- **Rate Limiting**: Generous for reasonable use
- **Scraping Strategy**:
  - Use Playwright with stealth mode
  - Wait for `.ups-tracking-status` selector
  - Extract JSON data from page state
  - Parse event timeline
  - Handle invalid tracking numbers gracefully

### 2. FedEx (fedex.com)

- **Tracking URL**: `https://www.fedex.com/fedextrack/?tracknumbers={tracking_number}`
- **Challenge**: React-based SPA, requires full page rendering
- **Anti-bot Protection**: Strong - Akamai bot detection, requires advanced stealth
- **Data Location**: Embedded in page state or intercepted API calls
- **Rate Limiting**: Strict - may block after 20-30 requests/hour from same IP
- **Scraping Strategy**:
  - Enhanced stealth (random viewport, genuine user agent)
  - Wait for `.tracking-details` selector
  - Intercept network requests for API data
  - Implement CAPTCHA detection
  - Add 30-second cooldown between requests
  - Store cookies between requests

### 3. Day & Ross (dayross.com)

- **Tracking URL**: `https://www.dayross.com/tracking/`
- **Challenge**: Canadian LTL carrier, simpler infrastructure
- **Anti-bot Protection**: Low - basic form submission
- **Data Location**: Server-side rendered HTML tables
- **Rate Limiting**: Minimal
- **Scraping Strategy**:
  - Submit form with tracking number
  - Parse HTML table with BeautifulSoup
  - Extract status, origin, destination, events
  - Straightforward implementation

### 4. Polaris Transportation (polaristransport.com)

- **Tracking URL**: **Must be manually confirmed before coding** — visit the site and locate the tracking page. Likely `https://www.polaristransport.com/tracking/` but not guaranteed.
- **Challenge**: Regional carrier, likely simpler site
- **Anti-bot Protection**: Low to moderate (needs testing with real tracking numbers)
- **Data Location**: Likely HTML-based (confirm before assuming)
- **Rate Limiting**: Unknown — test conservatively (5+ second delays initially)
- **Pre-implementation checklist:**
  1. Visit the live site and find the tracking page URL
  2. Identify whether it uses form submission or URL-based tracking
  3. Inspect the HTML output structure (DevTools → Network tab)
  4. Obtain 2-3 real tracking numbers for testing
- **Scraping Strategy (tentative — verify against live site):**
  - Similar to Day & Ross (form submit → parse HTML)
  - Implement fallback selector patterns
  - Log full page HTML on parse failure for debugging

---

## Implementation Steps

### Phase 1: Project Setup & Environment Configuration

#### Step 1.1: Initialize Project Structure

Create a well-organized project directory:

```
shipment-tracker/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application entry
│   │   ├── config.py            # Configuration and environment variables
│   │   ├── database.py          # Database connection and session management
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic validation schemas
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py        # Login, register, logout endpoints
│   │   │   ├── utils.py         # JWT token generation, password hashing
│   │   │   └── dependencies.py  # Auth middleware
│   │   ├── tracking/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py        # Tracking CRUD endpoints
│   │   │   ├── scrapers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py      # Base scraper class interface
│   │   │   │   ├── ups.py       # UPS specific scraper
│   │   │   │   ├── fedex.py     # FedEx specific scraper
│   │   │   │   ├── dayross.py   # Day & Ross specific scraper
│   │   │   │   └── polaris.py   # Polaris specific scraper
│   │   │   └── scheduler.py     # Background job for auto-refresh & cleanup
│   │   └── utils.py             # General utilities
│   ├── requirements.txt
│   ├── Dockerfile              # For Render deployment
│   └── alembic/                # Database migrations
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Auth/
│   │   │   │   ├── Login.jsx
│   │   │   │   └── Register.jsx
│   │   │   ├── Dashboard/
│   │   │   │   ├── Dashboard.jsx
│   │   │   │   ├── TrackingForm.jsx
│   │   │   │   ├── TrackingList.jsx
│   │   │   │   └── TrackingCard.jsx
│   │   │   └── Layout/
│   │   │       ├── Header.jsx
│   │   │       └── Sidebar.jsx
│   │   ├── services/
│   │   │   └── api.js          # API client with axios
│   │   ├── utils/
│   │   │   └── auth.js         # Token management
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── .env.example
└── README.md
```

#### Step 1.2: Install Backend Dependencies

Create `requirements.txt`:

```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
asyncpg==0.29.0
psycopg2-binary==2.9.9
alembic==1.13.1
pydantic==2.5.3
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
playwright==1.40.0
playwright-stealth==1.0.0
apscheduler==3.10.4
httpx==0.26.0
beautifulsoup4==4.12.3
lxml==5.1.0
python-dotenv==1.0.0
slowapi==0.1.9
```

Install dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium   # Install OS-level browser dependencies
```

#### Step 1.3: Install Frontend Dependencies

Initialize React with Vite:

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install axios react-router-dom
npm install @headlessui/react @heroicons/react
npm install tailwindcss postcss autoprefixer -D
npx tailwindcss init -p
```

---

### Phase 2: Database Design & Setup

#### Step 2.1: Design Database Schema

##### Users Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```

##### TrackingNumbers Table

```sql
CREATE TABLE tracking_numbers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tracking_number VARCHAR(100) NOT NULL,
    carrier VARCHAR(20) NOT NULL CHECK (carrier IN ('UPS', 'FEDEX', 'DAYROSS', 'POLARIS')),
    status VARCHAR(50),
    current_location VARCHAR(255),
    estimated_delivery DATE,
    delivered_date DATE,
    last_updated TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delete_at TIMESTAMP,
    raw_data JSONB,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    INDEX idx_tracking_number (tracking_number),
    INDEX idx_user_id (user_id),
    INDEX idx_delete_at (delete_at),
    INDEX idx_last_updated (last_updated)
);
```

##### TrackingEvents Table

```sql
CREATE TABLE tracking_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tracking_id UUID REFERENCES tracking_numbers(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    location VARCHAR(255),
    status VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Step 2.2: Setup Database Connection

In `database.py`:

- Create SQLAlchemy async engine
- Connection string: `postgresql://user:password@host:5432/dbname`
- Implement `get_db()` dependency for FastAPI
- Configure connection pooling

#### Step 2.3: Initialize Alembic for Migrations

```bash
alembic init alembic
# Edit alembic.ini with DATABASE_URL
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

---

### Phase 3: Authentication System

#### Step 3.1: Implement JWT Authentication _(parallel with Step 2.3)_

In `auth/utils.py`, create:

- `hash_password(password: str) -> str` - Uses bcrypt
- `verify_password(plain: str, hashed: str) -> bool` - Validates login
- `create_access_token(data: dict) -> str` - Generates JWT (24h expiration)
- `decode_access_token(token: str) -> dict` - Validates and decodes JWT

#### Step 3.2: Create Auth Routes _(depends on 3.1)_

**POST /api/auth/register**

- Validate email format
- Ensure password is 8+ characters
- Hash password
- Create user record
- Return JWT token + user info

**POST /api/auth/login**

- Verify email exists
- Verify password matches
- Update last_login timestamp
- Return JWT token + user info

**GET /api/auth/me**

- Validate JWT from Authorization header
- Return current user info

**POST /api/auth/logout**

- Client-side token removal (stateless JWT)

#### Step 3.3: Create Auth Middleware _(depends on 3.1)_

In `auth/dependencies.py`:

- `get_current_user()` dependency
  - Extract token from `Authorization: Bearer {token}` header
  - Decode and validate JWT
  - Fetch user from database
  - Raise 401 Unauthorized if invalid/expired

- `get_current_admin()` dependency (used by Phase 6 admin endpoints)
  - Calls `get_current_user()` first
  - Checks `user.is_admin == True`
  - Raise 403 Forbidden if user is not an admin

  ```python
  async def get_current_admin(
      current_user: User = Depends(get_current_user)
  ) -> User:
      if not current_user.is_admin:
          raise HTTPException(status_code=403, detail="Admin access required")
      return current_user
  ```

  > Note: For the initial build, you can manually set `is_admin=True` in the database for your own account using a direct SQL UPDATE. No admin UI needed.

---

### Phase 4: Web Scraping Implementation

#### Step 4.1: Create Base Scraper Class _(parallel with Phase 3)_

In `tracking/scrapers/base.py`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseScraper(ABC):
    @abstractmethod
    async def scrape(self, tracking_number: str) -> Dict[str, Any]:
        """
        Scrape tracking data from carrier website.

        Returns:
            {
                'status': str,              # 'In Transit', 'Delivered', 'Exception', etc.
                'current_location': str,    # City, State/Province
                'estimated_delivery': date, # Expected delivery date
                'delivered_date': date,     # Actual delivery date (if delivered)
                'events': [                 # Timeline of tracking events
                    {
                        'timestamp': datetime,
                        'location': str,
                        'status': str,
                        'description': str
                    }
                ],
                'error': str or None        # Error message if scraping failed
            }
        """
        pass
```

#### Step 4.2: Implement UPS Scraper _(depends on 4.1)_

In `tracking/scrapers/ups.py`:

**Key Implementation Details:**

1. Initialize Playwright browser with stealth mode
2. Navigate to `https://www.ups.com/track?tracknum={tracking_number}`
3. Wait for tracking data to load (selector: `.ups-tracking-status`)
4. Extract status, location, delivery date
5. Parse event timeline from tracking history
6. Handle errors:
   - Invalid tracking number
   - Page timeout (30 seconds max)
   - Anti-bot detection (return error for retry)
7. Implement retry logic with exponential backoff (3 attempts)
8. Add random delays (2-5 seconds) between actions

**Sample Code Structure:**

```python
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import random
import asyncio

class UPSScraper(BaseScraper):
    async def scrape(self, tracking_number: str) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/Toronto',
            )
            page = await context.new_page()
            await stealth_async(page)  # Apply stealth patches to bypass bot detection

            try:
                await page.goto(f'https://www.ups.com/track?tracknum={tracking_number}')
                await asyncio.sleep(random.uniform(2, 5))

                # Wait for tracking status
                await page.wait_for_selector('.ups-tracking-status', timeout=30000)

                # Extract data
                status = await page.text_content('.ups-tracking-status')
                # ... extract other fields

                return {
                    'status': status,
                    'current_location': location,
                    'estimated_delivery': est_delivery,
                    'delivered_date': delivered_date,
                    'events': events,
                    'error': None
                }
            except Exception as e:
                return {'error': str(e)}
            finally:
                await browser.close()
```

#### Step 4.3: Implement FedEx Scraper _(depends on 4.1)_

In `tracking/scrapers/fedex.py`:

**Key Implementation Details:**

1. Use Playwright with enhanced stealth:
   - Random viewport dimensions
   - Genuine user agent rotation
   - Extra headers to mimic real browser
2. Navigate to `https://www.fedex.com/fedextrack/?tracknumbers={tracking_number}`
3. Wait for React app to render (selector: `.tracking-details`)
4. Extract data from page state or intercept API calls:
   ```python
   page.on('response', lambda response: handle_response(response))
   ```
5. Parse delivery status and event timeline
6. Implement CAPTCHA detection:
   - Check for CAPTCHA elements
   - Return error if detected (manual retry needed)
7. Handle rate limiting:
   - Detect rate limit errors
   - Implement 30-second cooldown
8. Store cookies between requests for same session

**Anti-Detection Measures:**

- Randomize timing between actions
- Scroll page naturally
- Move cursor randomly
- Don't click too fast

#### Step 4.4: Implement Day & Ross Scraper _(depends on 4.1)_

In `tracking/scrapers/dayross.py`:

**Key Implementation Details:**

1. Navigate to `https://www.dayross.com/tracking/`
2. Locate tracking form input
3. Submit tracking number via form
4. Wait for results page
5. Parse HTML table with BeautifulSoup:
   ```python
   from bs4 import BeautifulSoup
   html = await page.content()
   soup = BeautifulSoup(html, 'lxml')
   ```
6. Extract status, origin, destination, events from table rows
7. Simpler implementation due to server-side rendering (no JavaScript delays)

**Expected HTML Structure:**

```html
<table class="tracking-results">
  <tr>
    <td>Status:</td>
    <td>In Transit</td>
  </tr>
  <tr>
    <td>Current Location:</td>
    <td>Toronto, ON</td>
  </tr>
  <!-- Event timeline -->
</table>
```

#### Step 4.5: Implement Polaris Transportation Scraper _(depends on 4.1)_

In `tracking/scrapers/polaris.py`:

**Research Phase:**

1. Visit `https://www.polaristransport.com/` to find tracking page
2. Test with sample tracking numbers (obtain from company if needed)
3. Analyze page structure (likely similar to Day & Ross)

**Implementation (Similar to Day & Ross):**

1. Navigate to tracking page
2. Submit form
3. Parse results
4. Implement fallback for structure changes
5. Add error handling for site unavailability

**Fallback Strategy:**
If site structure changes frequently:

- Store multiple selector patterns
- Try each pattern until one works
- Log failures for manual inspection

#### Step 4.6: Create Scraper Factory _(depends on 4.2-4.5)_

In `tracking/scrapers/__init__.py`:

```python
from typing import Dict
from .base import BaseScraper
from .ups import UPSScraper
from .fedex import FedExScraper
from .dayross import DayRossScraper
from .polaris import PolarisScraper

_scrapers: Dict[str, BaseScraper] = {
    'UPS': UPSScraper(),
    'FEDEX': FedExScraper(),
    'DAYROSS': DayRossScraper(),
    'POLARIS': PolarisScraper()
}

def get_scraper(carrier: str) -> BaseScraper:
    """Get scraper instance for specified carrier."""
    if carrier not in _scrapers:
        raise ValueError(f"Unknown carrier: {carrier}")
    return _scrapers[carrier]
```

**Browser Context Management:**

- Reuse browser instance across requests (saves memory)
- Close browser on application shutdown
- Implement request queuing to prevent parallel requests to same carrier

---

### Phase 5: Tracking API Endpoints

#### Step 5.1: Create Tracking Routes _(depends on Phase 3 & 4.6)_

In `tracking/routes.py`:

**POST /api/tracking/add**

```python
@router.post("/add")
async def add_tracking(
    data: AddTrackingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add multiple tracking numbers.

    Request body:
    {
        "carrier": "UPS",
        "tracking_numbers": ["1Z999AA10123456784", "1Z999AA10123456785"]
    }
    """
    # Validate carrier
    if data.carrier not in ['UPS', 'FEDEX', 'DAYROSS', 'POLARIS']:
        raise HTTPException(400, "Invalid carrier")

    # Create database records
    tracking_ids = []
    for number in data.tracking_numbers:
        tracking = TrackingNumber(
            user_id=current_user.id,
            tracking_number=number,
            carrier=data.carrier,
            status='Pending',
            last_updated=datetime.utcnow()
        )
        db.add(tracking)
        tracking_ids.append(tracking.id)

    db.commit()

    # Queue scraping jobs (async, don't wait)
    background_tasks.add_task(scrape_multiple, tracking_ids)

    return {"message": f"Added {len(tracking_ids)} tracking numbers", "ids": tracking_ids}
```

**GET /api/tracking/list**

```python
@router.get("/list")
async def list_tracking(
    page: int = 1,
    per_page: int = 20,
    status_filter: str = None,
    carrier_filter: str = None,
    search: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch all tracking numbers for current user with pagination and filters."""
    query = db.query(TrackingNumber).filter(
        TrackingNumber.user_id == current_user.id,
        or_(
            TrackingNumber.delete_at.is_(None),
            TrackingNumber.delete_at > datetime.utcnow()
        )
    )

    # Apply filters
    if status_filter:
        query = query.filter(TrackingNumber.status == status_filter)
    if carrier_filter:
        query = query.filter(TrackingNumber.carrier == carrier_filter)
    if search:
        query = query.filter(TrackingNumber.tracking_number.ilike(f"%{search}%"))

    # Pagination
    total = query.count()
    tracking = query.order_by(TrackingNumber.created_at.desc()) \
                    .offset((page - 1) * per_page) \
                    .limit(per_page) \
                    .all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "data": tracking
    }
```

**GET /api/tracking/{tracking_id}**

```python
@router.get("/{tracking_id}")
async def get_tracking(
    tracking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch specific tracking with all events."""
    tracking = db.query(TrackingNumber).filter(
        TrackingNumber.id == tracking_id,
        TrackingNumber.user_id == current_user.id
    ).first()

    if not tracking:
        raise HTTPException(404, "Tracking not found")

    # Include events
    events = db.query(TrackingEvent).filter(
        TrackingEvent.tracking_id == tracking_id
    ).order_by(TrackingEvent.timestamp.desc()).all()

    return {
        "tracking": tracking,
        "events": events
    }
```

**POST /api/tracking/{tracking_id}/refresh**

```python
@router.post("/{tracking_id}/refresh")
async def refresh_tracking(
    tracking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks
):
    """Manually trigger re-scraping."""
    tracking = db.query(TrackingNumber).filter(
        TrackingNumber.id == tracking_id,
        TrackingNumber.user_id == current_user.id
    ).first()

    if not tracking:
        raise HTTPException(404, "Tracking not found")

    # Queue scraping job
    background_tasks.add_task(scrape_and_update, tracking_id)

    return {"message": "Refresh queued"}
```

**DELETE /api/tracking/{tracking_id}**

```python
@router.delete("/{tracking_id}")
async def delete_tracking(
    tracking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Soft delete tracking (set delete_at to now)."""
    tracking = db.query(TrackingNumber).filter(
        TrackingNumber.id == tracking_id,
        TrackingNumber.user_id == current_user.id
    ).first()

    if not tracking:
        raise HTTPException(404, "Tracking not found")

    tracking.delete_at = datetime.utcnow()
    db.commit()

    return {"message": "Tracking deleted"}
```

#### Step 5.2: Implement Scraping Logic _(depends on 5.1)_

```python
async def scrape_and_update(tracking_id: UUID):
    """Scrape tracking data and update database."""
    db = SessionLocal()

    try:
        # Fetch tracking record
        tracking = db.query(TrackingNumber).filter(
            TrackingNumber.id == tracking_id
        ).first()

        if not tracking:
            return

        # Get appropriate scraper
        scraper = get_scraper(tracking.carrier)

        # Execute scrape
        result = await scraper.scrape(tracking.tracking_number)

        # Update database
        if result.get('error'):
            tracking.error_message = result['error']
            tracking.retry_count += 1
            if tracking.retry_count > 5:
                tracking.status = 'Failed'
        else:
            tracking.status = result['status']
            tracking.current_location = result.get('current_location')
            tracking.estimated_delivery = result.get('estimated_delivery')
            tracking.delivered_date = result.get('delivered_date')
            tracking.raw_data = result
            tracking.error_message = None

            # Set delete_at if delivered
            if result['status'] == 'Delivered' and result.get('delivered_date'):
                tracking.delete_at = result['delivered_date'] + timedelta(days=3)

            # Create event records
            for event in result.get('events', []):
                # Check if event already exists
                existing = db.query(TrackingEvent).filter(
                    TrackingEvent.tracking_id == tracking_id,
                    TrackingEvent.timestamp == event['timestamp'],
                    TrackingEvent.description == event['description']
                ).first()

                if not existing:
                    db.add(TrackingEvent(
                        tracking_id=tracking_id,
                        timestamp=event['timestamp'],
                        location=event['location'],
                        status=event['status'],
                        description=event['description']
                    ))

        tracking.last_updated = datetime.utcnow()
        db.commit()

    finally:
        db.close()
```

#### Step 5.3: Implement Batch Scraping _(depends on 5.2)_

```python
async def scrape_multiple(tracking_ids: List[UUID]):
    """Scrape multiple tracking numbers with rate limiting."""
    db = SessionLocal()

    try:
        # Fetch all tracking records
        trackings = db.query(TrackingNumber).filter(
            TrackingNumber.id.in_(tracking_ids)
        ).all()

        # Group by carrier
        by_carrier = {}
        for tracking in trackings:
            if tracking.carrier not in by_carrier:
                by_carrier[tracking.carrier] = []
            by_carrier[tracking.carrier].append(tracking.id)

        # Process sequentially per carrier, parallel across carriers
        tasks = []
        for carrier, ids in by_carrier.items():
            tasks.append(scrape_carrier_batch(carrier, ids))

        await asyncio.gather(*tasks)

    finally:
        db.close()


async def scrape_carrier_batch(carrier: str, tracking_ids: List[UUID]):
    """Scrape tracking IDs for a specific carrier with delays."""
    for tracking_id in tracking_ids:
        await scrape_and_update(tracking_id)
        # Add delay between requests to same carrier
        await asyncio.sleep(random.uniform(5, 10))
```

---

### Phase 6: Background Job Scheduler

#### Step 6.1: Setup APScheduler _(depends on Step 5.2)_

In `tracking/scheduler.py`:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)

# IMPORTANT: Use AsyncIOScheduler (not BackgroundScheduler) because the job
# functions are async. BackgroundScheduler runs jobs in a thread pool and
# cannot await coroutines.
scheduler = AsyncIOScheduler()

def start_scheduler():
    """Initialize and start the scheduler."""
    scheduler.add_job(
        auto_refresh_tracking,
        trigger=IntervalTrigger(hours=3),
        id='auto_refresh',
        name='Auto-refresh undelivered tracking',
        replace_existing=True
    )

    scheduler.add_job(
        cleanup_old_tracking,
        trigger=CronTrigger(hour=2, minute=0),  # Run at 2 AM daily
        id='cleanup',
        name='Cleanup old tracking',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Scheduler started")

def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    scheduler.shutdown()
    logger.info("Scheduler shut down")
```

#### Step 6.2: Create Auto-Refresh Job _(depends on 6.1)_

```python
async def auto_refresh_tracking():
    """Auto-refresh undelivered tracking numbers every 3 hours."""
    logger.info("Starting auto-refresh job")
    db = SessionLocal()

    try:
        # Query tracking numbers that need refresh
        three_hours_ago = datetime.utcnow() - timedelta(hours=3)
        tracking_to_refresh = db.query(TrackingNumber).filter(
            TrackingNumber.status != 'Delivered',
            TrackingNumber.last_updated < three_hours_ago,
            or_(
                TrackingNumber.delete_at.is_(None),
                TrackingNumber.delete_at > datetime.utcnow()
            )
        ).all()

        tracking_ids = [t.id for t in tracking_to_refresh]
        logger.info(f"Found {len(tracking_ids)} tracking numbers to refresh")

        # Batch scrape
        if tracking_ids:
            await scrape_multiple(tracking_ids)

        logger.info("Auto-refresh job completed")

    except Exception as e:
        logger.error(f"Auto-refresh job failed: {e}")
    finally:
        db.close()
```

#### Step 6.3: Create Cleanup Job _(depends on 6.1)_

```python
async def cleanup_old_tracking():
    """Delete tracking data 3 days after delivery (runs daily at 2 AM)."""
    logger.info("Starting cleanup job")
    db = SessionLocal()

    try:
        # Query tracking numbers past delete_at
        to_delete = db.query(TrackingNumber).filter(
            TrackingNumber.delete_at < datetime.utcnow()
        ).all()

        count = len(to_delete)
        logger.info(f"Found {count} tracking numbers to delete")

        # Delete records (cascade will delete events)
        for tracking in to_delete:
            db.delete(tracking)

        db.commit()
        logger.info(f"Cleanup job completed: deleted {count} records")

    except Exception as e:
        logger.error(f"Cleanup job failed: {e}")
        db.rollback()
    finally:
        db.close()
```

#### Step 6.3.1: Handle Render Free Tier Sleep _(important constraint)_

**Problem:** Render free tier sleeps the service after 15 minutes of inactivity. When the service wakes, `APScheduler` restarts fresh with no memory of missed jobs. A 3-hour refresh cycle may be missed entirely if no one uses the app.

**Mitigation strategies (pick one):**

1. **Trigger on request (simplest)** — In `list_tracking`, check if any undelivered shipments haven't been updated in 3+ hours and queue a background refresh. This piggybacks on user activity.

   ```python
   # In list_tracking endpoint, after fetching results:
   stale = [t for t in tracking if t.status != 'Delivered'
            and (datetime.utcnow() - t.last_updated) > timedelta(hours=3)]
   if stale:
       background_tasks.add_task(scrape_multiple, [t.id for t in stale])
   ```

2. **External cron ping** — Use a free service (cron-job.org, UptimeRobot) to call `POST /api/admin/jobs/trigger-refresh` every 3 hours. This also prevents the service from sleeping.

3. **Accept the limitation** — If users interact regularly, the scheduler will run. Document the behavior: "Auto-refresh runs every 3 hours while the service is active."

**Recommendation:** Use option 2 (external ping) — it solves both the sleep problem and the scheduler reliability problem at zero cost.

#### Step 6.4: Add Job Management Endpoints _(depends on 6.2-6.3)_

```python
@router.get("/admin/jobs/status")
async def get_job_status(current_user: User = Depends(get_current_admin)):
    """Return scheduler status and next run times (admin only)."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
        })

    return {
        'running': scheduler.running,
        'jobs': jobs
    }

@router.post("/admin/jobs/trigger-refresh")
async def trigger_refresh(current_user: User = Depends(get_current_admin)):
    """Manually trigger auto-refresh job (admin only)."""
    await auto_refresh_tracking()
    return {"message": "Refresh job triggered"}

@router.post("/admin/jobs/trigger-cleanup")
async def trigger_cleanup(current_user: User = Depends(get_current_admin)):
    """Manually trigger cleanup job (admin only)."""
    await cleanup_old_tracking()
    return {"message": "Cleanup job triggered"}
```

---

### Phase 7: Frontend Development

#### Step 7.1: Setup Tailwind CSS & Base Styles _(parallel with backend)_

**Configure `tailwind.config.js`:**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eff6ff",
          500: "#2563eb",
          600: "#1d4ed8",
          700: "#1e40af",
        },
        success: {
          500: "#10b981",
          600: "#059669",
        },
        warning: {
          500: "#f59e0b",
          600: "#d97706",
        },
        error: {
          500: "#ef4444",
          600: "#dc2626",
        },
      },
    },
  },
  plugins: [],
};
```

**Create base CSS in `src/index.css`:**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer components {
  .btn {
    @apply px-4 py-2 rounded-lg font-medium transition-colors;
  }

  .btn-primary {
    @apply bg-primary-500 text-white hover:bg-primary-600;
  }

  .btn-secondary {
    @apply bg-gray-200 text-gray-800 hover:bg-gray-300;
  }

  .input {
    @apply border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500;
  }

  .card {
    @apply bg-white rounded-lg shadow-md p-6;
  }
}
```

#### Step 7.1.1: Implement App Routing & Auth Guard _(depends on 7.1)_

**src/utils/auth.js** — Token and user management utilities:

```javascript
export const getToken = () => localStorage.getItem('token');

export const getUser = () => {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null');
  } catch {
    return null;
  }
};

export const setAuth = (token, user) => {
  localStorage.setItem('token', token);
  localStorage.setItem('user', JSON.stringify(user));
};

export const clearAuth = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
};

export const isAuthenticated = () => !!getToken();
```

**src/App.jsx** — Root component with routing and protected route guard:

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './components/Layout/Toast';
import Login from './components/Auth/Login';
import Register from './components/Auth/Register';
import Dashboard from './components/Dashboard/Dashboard';
import { isAuthenticated } from './utils/auth';

function ProtectedRoute({ children }) {
  return isAuthenticated() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
```

#### Step 7.2: Build Authentication Pages _(depends on 7.1)_

**Login.jsx:**

```jsx
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login } from "../../services/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await login(email, password);
      localStorage.setItem("token", response.token);
      localStorage.setItem("user", JSON.stringify(response.user));
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.data?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card max-w-md w-full">
        <h2 className="text-2xl font-bold text-center mb-6">
          Shipment Tracker Login
        </h2>

        {error && (
          <div className="bg-error-50 border border-error-500 text-error-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-gray-700 mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input w-full"
              required
            />
          </div>

          <div className="mb-6">
            <label className="block text-gray-700 mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input w-full"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary w-full"
          >
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="text-center mt-4 text-gray-600">
          Don't have an account?{" "}
          <Link to="/register" className="text-primary-500 hover:underline">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}
```

**Register.jsx:**

```jsx
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { register } from "../../services/api";

export default function Register() {
  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    // Validation
    if (formData.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);

    try {
      const response = await register(
        formData.username,
        formData.email,
        formData.password,
      );
      localStorage.setItem("token", response.token);
      localStorage.setItem("user", JSON.stringify(response.user));
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.data?.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card max-w-md w-full">
        <h2 className="text-2xl font-bold text-center mb-6">Create Account</h2>

        {error && (
          <div className="bg-error-50 border border-error-500 text-error-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-gray-700 mb-2">Username</label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              className="input w-full"
              required
            />
          </div>

          <div className="mb-4">
            <label className="block text-gray-700 mb-2">Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className="input w-full"
              required
            />
          </div>

          <div className="mb-4">
            <label className="block text-gray-700 mb-2">Password</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className="input w-full"
              required
            />
          </div>

          <div className="mb-6">
            <label className="block text-gray-700 mb-2">Confirm Password</label>
            <input
              type="password"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              className="input w-full"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary w-full"
          >
            {loading ? "Creating account..." : "Register"}
          </button>
        </form>

        <p className="text-center mt-4 text-gray-600">
          Already have an account?{" "}
          <Link to="/login" className="text-primary-500 hover:underline">
            Login
          </Link>
        </p>
      </div>
    </div>
  );
}
```

#### Step 7.3: Build Dashboard Layout _(depends on 7.1)_

**Header.jsx:**

```jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function Header() {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("/login");
  };

  return (
    <header className="bg-white shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
        <div className="flex items-center">
          <h1 className="text-2xl font-bold text-primary-500">
            📦 Shipment Tracker
          </h1>
        </div>

        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center space-x-2 hover:bg-gray-100 px-3 py-2 rounded-lg"
          >
            <span className="font-medium">{user.username}</span>
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg py-1">
              <button
                onClick={handleLogout}
                className="block w-full text-left px-4 py-2 hover:bg-gray-100"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
```

**Dashboard.jsx:**

```jsx
import { useState } from "react";
import Header from "../Layout/Header";
import TrackingForm from "./TrackingForm";
import TrackingList from "./TrackingList";

export default function Dashboard() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleTrackingAdded = () => {
    // Trigger refresh of tracking list
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-7xl mx-auto px-4 py-8">
        <TrackingForm onSuccess={handleTrackingAdded} />
        <TrackingList key={refreshTrigger} />
      </main>
    </div>
  );
}
```

#### Step 7.4: Build Tracking Form Component _(depends on 7.3)_

**TrackingForm.jsx:**

```jsx
import { useState } from "react";
import { addTracking } from "../../services/api";

export default function TrackingForm({ onSuccess }) {
  const [carrier, setCarrier] = useState("UPS");
  const [trackingNumbers, setTrackingNumbers] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const carriers = [
    { value: "UPS", label: "UPS" },
    { value: "FEDEX", label: "FedEx" },
    { value: "DAYROSS", label: "Day & Ross" },
    { value: "POLARIS", label: "Polaris Transportation" },
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    // Parse tracking numbers (one per line)
    const numbers = trackingNumbers
      .split("\n")
      .map((n) => n.trim())
      .filter((n) => n.length > 0);

    if (numbers.length === 0) {
      setError("Please enter at least one tracking number");
      setLoading(false);
      return;
    }

    try {
      await addTracking(carrier, numbers);
      setSuccess(`Added ${numbers.length} tracking number(s)`);
      setTrackingNumbers("");
      setTimeout(() => setSuccess(""), 3000);
      onSuccess?.();
    } catch (err) {
      setError(err.response?.data?.message || "Failed to add tracking");
    } finally {
      setLoading(false);
    }
  };

  const numberCount = trackingNumbers
    .split("\n")
    .map((n) => n.trim())
    .filter((n) => n.length > 0).length;

  return (
    <div className="card mb-8">
      <h2 className="text-xl font-bold mb-4">Add Tracking Numbers</h2>

      {error && (
        <div className="bg-error-50 border border-error-500 text-error-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-success-50 border border-success-500 text-success-700 px-4 py-3 rounded mb-4">
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="grid md:grid-cols-4 gap-4 mb-4">
          <div className="md:col-span-1">
            <label className="block text-gray-700 mb-2">Carrier</label>
            <select
              value={carrier}
              onChange={(e) => setCarrier(e.target.value)}
              className="input w-full"
            >
              {carriers.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="block text-gray-700 mb-2">
              Tracking Numbers (one per line)
              {numberCount > 0 && (
                <span className="text-gray-500 ml-2">
                  ({numberCount} number{numberCount !== 1 ? "s" : ""})
                </span>
              )}
            </label>
            <textarea
              value={trackingNumbers}
              onChange={(e) => setTrackingNumbers(e.target.value)}
              className="input w-full"
              rows="3"
              placeholder="1Z999AA10123456784&#10;1Z999AA10123456785&#10;1Z999AA10123456786"
              required
            />
          </div>
        </div>

        <button type="submit" disabled={loading} className="btn btn-primary">
          {loading ? "Adding..." : "Add Tracking"}
        </button>
      </form>
    </div>
  );
}
```

#### Step 7.5: Build Tracking List Component _(depends on 7.3)_

**TrackingList.jsx:**

```jsx
import { useState, useEffect } from "react";
import { listTracking } from "../../services/api";
import TrackingCard from "./TrackingCard";

export default function TrackingList() {
  const [tracking, setTracking] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: "",
    carrier: "",
    search: "",
  });

  const fetchTracking = async () => {
    try {
      const response = await listTracking(filters);
      setTracking(response.data);
    } catch (err) {
      console.error("Failed to fetch tracking:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTracking();

    // Poll for updates every 30 seconds
    const interval = setInterval(fetchTracking, 30000);
    return () => clearInterval(interval);
  }, [filters]);

  const handleTrackingUpdated = () => {
    fetchTracking();
  };

  if (loading) {
    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card animate-pulse">
            <div className="h-6 bg-gray-200 rounded mb-4"></div>
            <div className="h-4 bg-gray-200 rounded mb-2"></div>
            <div className="h-4 bg-gray-200 rounded"></div>
          </div>
        ))}
      </div>
    );
  }

  if (tracking.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">No tracking numbers yet</p>
        <p className="text-gray-400">
          Add tracking numbers above to get started
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap gap-4">
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          className="input"
        >
          <option value="">All Statuses</option>
          <option value="In Transit">In Transit</option>
          <option value="Delivered">Delivered</option>
          <option value="Out for Delivery">Out for Delivery</option>
          <option value="Exception">Exception</option>
        </select>

        <select
          value={filters.carrier}
          onChange={(e) => setFilters({ ...filters, carrier: e.target.value })}
          className="input"
        >
          <option value="">All Carriers</option>
          <option value="UPS">UPS</option>
          <option value="FEDEX">FedEx</option>
          <option value="DAYROSS">Day & Ross</option>
          <option value="POLARIS">Polaris</option>
        </select>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tracking.map((item) => (
          <TrackingCard
            key={item.id}
            tracking={item}
            onUpdate={handleTrackingUpdated}
          />
        ))}
      </div>
    </div>
  );
}
```

#### Step 7.6: Build Tracking Card Component _(depends on 7.5)_

**TrackingCard.jsx:**

```jsx
import { useState } from "react";
import { refreshTracking, deleteTracking } from "../../services/api";

export default function TrackingCard({ tracking, onUpdate }) {
  const [expanded, setExpanded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshTracking(tracking.id);
      setTimeout(() => {
        onUpdate();
        setRefreshing(false);
      }, 2000);
    } catch (err) {
      console.error("Refresh failed:", err);
      setRefreshing(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Remove this tracking number?")) return;

    try {
      await deleteTracking(tracking.id);
      onUpdate();
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "Delivered":
        return "bg-success-500";
      case "In Transit":
        return "bg-primary-500";
      case "Out for Delivery":
        return "bg-warning-500";
      case "Exception":
        return "bg-error-500";
      default:
        return "bg-gray-500";
    }
  };

  const getRelativeTime = (date) => {
    const seconds = Math.floor((new Date() - new Date(date)) / 1000);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  return (
    <div className="card">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <p className="text-sm text-gray-500">{tracking.carrier}</p>
          <p className="font-bold text-lg">{tracking.tracking_number}</p>
        </div>
        <span
          className={`${getStatusColor(tracking.status)} text-white px-3 py-1 rounded-full text-sm`}
        >
          {tracking.status}
        </span>
      </div>

      {/* Current Location */}
      {tracking.current_location && (
        <div className="mb-3">
          <p className="text-sm text-gray-500">📍 Current Location</p>
          <p className="font-medium">{tracking.current_location}</p>
        </div>
      )}

      {/* Delivery Date */}
      {tracking.estimated_delivery && (
        <div className="mb-4">
          <p className="text-sm text-gray-500">
            {tracking.status === "Delivered"
              ? "✓ Delivered"
              : "📅 Estimated Delivery"}
          </p>
          <p className="font-medium">
            {new Date(tracking.estimated_delivery).toLocaleDateString()}
          </p>
        </div>
      )}

      {/* Timeline Toggle */}
      {tracking.events && tracking.events.length > 0 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-primary-500 text-sm hover:underline mb-4"
        >
          {expanded ? "Hide" : "Show"} Timeline ({tracking.events.length}{" "}
          events)
        </button>
      )}

      {/* Expanded Timeline */}
      {expanded && tracking.events && (
        <div className="border-t pt-4 mb-4">
          <div className="space-y-3">
            {tracking.events.map((event, idx) => (
              <div key={idx} className="flex">
                <div className="flex-shrink-0 w-2 h-2 rounded-full bg-primary-500 mt-2 mr-3"></div>
                <div>
                  <p className="text-sm font-medium">{event.status}</p>
                  <p className="text-xs text-gray-500">{event.location}</p>
                  <p className="text-xs text-gray-400">
                    {new Date(event.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Auto-delete countdown */}
      {tracking.delete_at && (
        <div className="bg-gray-50 rounded p-2 mb-4 text-xs text-gray-600">
          ⏱ Removing in{" "}
          {Math.ceil(
            (new Date(tracking.delete_at) - new Date()) / (1000 * 60 * 60 * 24),
          )}{" "}
          days
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-between items-center border-t pt-4">
        <p className="text-xs text-gray-500">
          Updated {getRelativeTime(tracking.last_updated)}
        </p>
        <div className="flex space-x-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="text-primary-500 hover:text-primary-600 text-sm p-2"
            title="Refresh"
          >
            {refreshing ? "⟳" : "↻"}
          </button>
          <button
            onClick={handleDelete}
            className="text-error-500 hover:text-error-600 text-sm p-2"
            title="Remove"
          >
            🗑
          </button>
        </div>
      </div>
    </div>
  );
}
```

#### Step 7.7: Implement API Integration _(depends on backend completion)_

**services/api.js:**

```javascript
import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor - add JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor - handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// Auth endpoints
export const login = async (email, password) => {
  const response = await api.post("/auth/login", { email, password });
  return response.data;
};

export const register = async (username, email, password) => {
  const response = await api.post("/auth/register", {
    username,
    email,
    password,
  });
  return response.data;
};

export const getCurrentUser = async () => {
  const response = await api.get("/auth/me");
  return response.data;
};

// Tracking endpoints
export const addTracking = async (carrier, trackingNumbers) => {
  const response = await api.post("/tracking/add", {
    carrier,
    tracking_numbers: trackingNumbers,
  });
  return response.data;
};

export const listTracking = async (filters = {}) => {
  const response = await api.get("/tracking/list", { params: filters });
  return response.data;
};

export const getTracking = async (id) => {
  const response = await api.get(`/tracking/${id}`);
  return response.data;
};

export const refreshTracking = async (id) => {
  const response = await api.post(`/tracking/${id}/refresh`);
  return response.data;
};

export const deleteTracking = async (id) => {
  const response = await api.delete(`/tracking/${id}`);
  return response.data;
};

export default api;
```

#### Step 7.8: Add Real-Time Updates _(depends on 7.5-7.7)_

Already implemented in TrackingList.jsx with 30-second polling:

```javascript
useEffect(() => {
  fetchTracking();

  // Poll for updates every 30 seconds
  const interval = setInterval(fetchTracking, 30000);
  return () => clearInterval(interval);
}, [filters]);
```

#### Step 7.9: Implement Responsive Design _(depends on 7.2-7.6)_

**Testing Checklist:**

- ✅ Mobile (320px): Single column layout, large touch targets
- ✅ Tablet (768px): 2-column grid for tracking cards
- ✅ Desktop (1024px+): 3-column grid for tracking cards
- ✅ All buttons minimum 44px height for touch
- ✅ Font sizes minimum 16px for body text
- ✅ No horizontal scroll on any screen size

**Responsive utilities already used:**

- `md:grid-cols-2` - 2 columns on medium screens
- `lg:grid-cols-3` - 3 columns on large screens
- `md:col-span-4` - Full width on medium screens
- `flex-wrap` - Wrapping for filter buttons

---

### Phase 8: Error Handling & User Experience

#### Step 8.1: Backend Error Handling _(parallel with Phase 5-6)_

**Global Exception Handler in `main.py`:**

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "details": {}
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail.get("error", "error"),
            "message": exc.detail.get("message", str(exc.detail)),
            "details": exc.detail.get("details", {})
        }
    )
```

**Rate Limiting with SlowAPI:**

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/add")
@limiter.limit("10/minute")
async def add_tracking(request: Request, ...):
    # Endpoint code
    pass
```

#### Step 8.2: Frontend Error Handling _(depends on 7.7)_

**Toast Notification Component:**

```jsx
import { createContext, useContext, useState } from "react";

const ToastContext = createContext();

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = "info") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`px-6 py-4 rounded-lg shadow-lg text-white ${
              toast.type === "error"
                ? "bg-error-500"
                : toast.type === "success"
                  ? "bg-success-500"
                  : toast.type === "warning"
                    ? "bg-warning-500"
                    : "bg-primary-500"
            }`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
```

**User-Friendly Error Messages:**

```javascript
const getFriendlyErrorMessage = (error) => {
  if (error.response?.status === 429) {
    return "Too many requests. Please wait a moment.";
  }
  if (error.response?.status === 404) {
    return "Tracking number not found.";
  }
  if (error.response?.status === 400) {
    return "Invalid tracking number format.";
  }
  if (!error.response) {
    return "Unable to connect. Please check your internet connection.";
  }
  return (
    error.response?.data?.message || "An error occurred. Please try again."
  );
};
```

#### Step 8.3: Loading States _(depends on Phase 7)_

**Already implemented in components:**

- Login/Register buttons: `{loading ? 'Logging in...' : 'Login'}`
- TrackingForm submit: `{loading ? 'Adding...' : 'Add Tracking'}`
- TrackingList skeleton screens while fetching
- TrackingCard refresh button: Spinner during refresh

#### Step 8.4: Add User Feedback _(depends on Phase 7)_

**Confirmation Dialog Component:**

```jsx
export function ConfirmDialog({ open, onConfirm, onCancel, message }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-sm">
        <p className="mb-6">{message}</p>
        <div className="flex justify-end space-x-3">
          <button onClick={onCancel} className="btn btn-secondary">
            Cancel
          </button>
          <button onClick={onConfirm} className="btn bg-error-500 text-white">
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Progress Indicator for Batch Operations:**

```jsx
{batchProgress && (
  <div className="bg-blue-50 border border-blue-500 text-blue-700 px-4 py-3 rounded">
    Adding {batchProgress.total} tracking numbers... {batchProgress.completed} of {batchProgress.total} complete
  </div>
)}
```

---

### Phase 9: Deployment Configuration

#### Step 9.1: Create Backend Dockerfile _(parallel with Phase 8)_

**backend/Dockerfile:**

```dockerfile
FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
RUN playwright install chromium

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Step 9.2: Configure Environment Variables _(depends on 9.1)_

**.env.example:**

```env
# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# JWT Configuration
SECRET_KEY=your-super-secret-32-character-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Environment
ENVIRONMENT=production
DEBUG=false

# Frontend URL (for CORS)
FRONTEND_URL=https://your-frontend.onrender.com

# Render specific (optional)
PORT=8000
```

**Generate SECRET_KEY:**

```python
import secrets
print(secrets.token_urlsafe(32))
```

#### Step 9.3: Setup PostgreSQL on Render _(parallel with 9.2)_

> **Warning:** Render free PostgreSQL databases **expire after 90 days** and are then deleted. After expiry you must either upgrade to a paid plan ($7/month) or recreate the database and re-run migrations (all data is lost). Plan for this before go-live — either upgrade at the 90-day mark or use Neon.tech as a free alternative (which has no expiry limit on free tier).

**Steps:**

1. Go to Render Dashboard → New → PostgreSQL
2. Select Free tier (90 days, then $7/month for 1GB)
3. Name: `shipment-tracker-db`
4. Region: Select closest to your users (Oregon for Canada/US)
5. Create Database
6. Copy Internal Database URL
7. Use Internal URL for DATABASE_URL (faster, free internal bandwidth)

#### Step 9.3.1: Add Health Check Endpoint _(required for Render)_

Render needs a health check path to know when the service is ready. Add to `app/main.py`:

```python
from fastapi import FastAPI
from sqlalchemy import text

app = FastAPI(title="Shipment Tracker API")

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for Render's health monitoring."""
    try:
        # Verify database connectivity
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected"}
        )
```

This endpoint is referenced in `render.yaml` as `healthCheckPath: /api/health`. Without it, Render will mark every deploy as failed.

#### Step 9.4: Deploy Backend to Render _(depends on 9.1-9.3)_

**Steps:**

1. Push code to GitHub repository
2. Go to Render Dashboard → New → Web Service
3. Connect GitHub repository
4. Configuration:
   - **Name**: `shipment-tracker-backend`
   - **Environment**: Docker
   - **Region**: Same as database
   - **Branch**: main
   - **Instance Type**: Free
   - **Health Check Path**: `/api/health`
5. Add Environment Variables (from .env.example)
6. Deploy

**Auto-deploy on Git push:** Enabled by default

#### Step 9.5: Build Frontend for Production _(depends on Phase 7)_

**Update frontend/.env:**

```env
VITE_API_URL=https://shipment-tracker-backend.onrender.com/api
```

**Build:**

```bash
cd frontend
npm run build
```

Output in `dist/` folder

#### Step 9.6: Deploy Frontend to Render _(depends on 9.5)_

**Steps:**

1. Go to Render Dashboard → New → Static Site
2. Connect GitHub repository
3. Configuration:
   - **Name**: `shipment-tracker-frontend`
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Publish Directory**: `frontend/dist`
4. Deploy

**Configure SPA Routing:**

Create `frontend/public/_redirects`:

```
/*    /index.html   200
```

#### Step 9.7: Configure CORS _(depends on 9.6)_

**In backend/app/main.py:**

```python
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL"),
        "http://localhost:5173",  # For local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Step 9.8: Run Database Migrations _(depends on 9.4)_

**Option 1: Manual (First time only)**

SSH into Render container:

```bash
alembic upgrade head
```

**Option 2: Automatic with render.yaml**

Create `render.yaml` in project root:

```yaml
services:
  - type: web
    name: shipment-tracker-backend
    env: docker
    region: oregon
    plan: free
    branch: main
    healthCheckPath: /api/health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: shipment-tracker-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: ALGORITHM
        value: HS256
      - key: ACCESS_TOKEN_EXPIRE_MINUTES
        value: 1440
      - key: ENVIRONMENT
        value: production
      - key: FRONTEND_URL
        value: https://shipment-tracker-frontend.onrender.com
    autoDeploy: true
    preDeployCommand: "alembic upgrade head"

  - type: web
    name: shipment-tracker-frontend
    env: static
    branch: main
    buildCommand: "cd frontend && npm install && npm run build"
    staticPublishPath: frontend/dist
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
    envVars:
      - key: VITE_API_URL
        value: https://shipment-tracker-backend.onrender.com/api

databases:
  - name: shipment-tracker-db
    plan: free
    region: oregon
```

---

### Phase 10: Testing & Optimization

#### Step 10.1: Test Scraping Functions _(depends on Phase 4)_

**Manual Testing Checklist:**

1. **UPS Testing:**
   - ✅ Valid tracking number (in transit)
   - ✅ Valid tracking number (delivered)
   - ✅ Invalid tracking number
   - ✅ Timeout handling
   - ✅ Anti-bot detection response

2. **FedEx Testing:**
   - ✅ Valid tracking number
   - ✅ Rate limit handling
   - ✅ CAPTCHA detection
   - ✅ Cookie persistence

3. **Day & Ross Testing:**
   - ✅ Valid tracking number
   - ✅ Invalid tracking number
   - ✅ HTML parsing accuracy

4. **Polaris Testing:**
   - ✅ Confirm URL structure
   - ✅ Test with sample numbers
   - ✅ Verify data extraction

**Automated Tests (Optional):**

```python
import pytest
from app.tracking.scrapers import get_scraper

@pytest.mark.asyncio
async def test_ups_scraper_valid():
    scraper = get_scraper('UPS')
    result = await scraper.scrape('1Z999AA10123456784')
    assert result['error'] is None
    assert result['status'] is not None

@pytest.mark.asyncio
async def test_ups_scraper_invalid():
    scraper = get_scraper('UPS')
    result = await scraper.scrape('INVALID')
    assert result['error'] is not None
```

#### Step 10.2: Load Testing _(depends on Phase 9)_

**Using Apache Bench (ab):**

```bash
# Test API endpoint with 10 concurrent users, 100 requests
ab -n 100 -c 10 -H "Authorization: Bearer YOUR_JWT_TOKEN" \
   https://shipment-tracker-backend.onrender.com/api/tracking/list
```

**Monitor Render Metrics:**

- Go to Render Dashboard → Service → Metrics
- Check:
  - Memory usage (must stay < 400MB)
  - CPU usage
  - Response times

**Test Auto-Refresh Job:**

1. Add 50+ tracking numbers
2. Wait for 3-hour interval
3. Check logs for auto-refresh execution
4. Verify tracking data updated

#### Step 10.3: Browser Testing _(depends on Phase 7)_

**Testing Matrix:**

| Browser | Version | Mobile | Desktop | Status |
| ------- | ------- | ------ | ------- | ------ |
| Chrome  | Latest  | ✓      | ✓       |        |
| Firefox | Latest  | ✓      | ✓       |        |
| Safari  | Latest  | ✓      | ✓       |        |
| Edge    | Latest  | -      | ✓       |        |

**User Flow Tests:**

1. ✅ Register new account
2. ✅ Login with credentials
3. ✅ Add single tracking number
4. ✅ Add multiple tracking numbers
5. ✅ View tracking details
6. ✅ Expand event timeline
7. ✅ Refresh tracking manually
8. ✅ Delete tracking
9. ✅ Logout
10. ✅ Login again (verify persistence)

#### Step 10.4: Security Audit _(depends on Phase 9)_

**Security Checklist:**

1. **Authentication:**
   - ✅ JWT tokens expire after 24 hours
   - ✅ Tokens validated on protected endpoints
   - ✅ Invalid tokens return 401
   - ✅ Passwords hashed with bcrypt

2. **Authorization:**
   - ✅ Users can only access own tracking data
   - ✅ Direct URL access to other users' data returns 404
   - ✅ Admin endpoints require admin role (if implemented)

3. **Input Validation:**
   - ✅ SQL injection prevented (SQLAlchemy parameterized queries)
   - ✅ XSS prevented (React auto-escapes)
   - ✅ CSRF not applicable (stateless API)

4. **Transport Security:**
   - ✅ HTTPS enforced on Render
   - ✅ Secure cookies (if using)
   - ✅ CORS configured correctly

5. **Rate Limiting:**
   - ✅ 10 requests/minute per user
   - ✅ 429 status returned when exceeded
   - ✅ Proper error messages

**Penetration Testing (Optional):**

- Use OWASP ZAP or Burp Suite
- Test for common vulnerabilities

#### Step 10.5: Performance Optimization _(depends on 10.2)_

**Database Indexes:**

```sql
-- Already in schema
CREATE INDEX idx_tracking_number ON tracking_numbers(tracking_number);
CREATE INDEX idx_user_id ON tracking_numbers(user_id);
CREATE INDEX idx_delete_at ON tracking_numbers(delete_at);
CREATE INDEX idx_last_updated ON tracking_numbers(last_updated);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
```

**Additional Optimizations:**

1. **Browser Reuse:**

   ```python
   # Share browser instance across requests
   _browser = None

   async def get_browser():
       global _browser
       if _browser is None:
           _browser = await playwright.chromium.launch()
       return _browser
   ```

2. **Query Optimization:**

   ```python
   # Use select_related to reduce queries
   tracking = db.query(TrackingNumber) \
               .options(selectinload(TrackingNumber.events)) \
               .filter(...).all()
   ```

3. **Response Compression:**

   ```python
   from fastapi.middleware.gzip import GZipMiddleware
   app.add_middleware(GZipMiddleware, minimum_size=1000)
   ```

4. **API Pagination:**
   Already implemented in list endpoint (20 per page)

---

## File Structure

### Complete Project Structure

```
shipment-tracker/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── utils.py
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   ├── utils.py
│   │   │   └── dependencies.py
│   │   └── tracking/
│   │       ├── __init__.py
│   │       ├── routes.py
│   │       ├── scheduler.py
│   │       └── scrapers/
│   │           ├── __init__.py
│   │           ├── base.py
│   │           ├── ups.py
│   │           ├── fedex.py
│   │           ├── dayross.py
│   │           └── polaris.py
│   ├── alembic/
│   │   ├── versions/
│   │   └── env.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic.ini
├── frontend/
│   ├── public/
│   │   └── _redirects        # SPA fallback routing for Render static site
│   ├── src/
│   │   ├── components/
│   │   │   ├── Auth/
│   │   │   │   ├── Login.jsx
│   │   │   │   └── Register.jsx
│   │   │   ├── Dashboard/
│   │   │   │   ├── Dashboard.jsx
│   │   │   │   ├── TrackingForm.jsx
│   │   │   │   ├── TrackingList.jsx
│   │   │   │   └── TrackingCard.jsx
│   │   │   └── Layout/
│   │   │       ├── Header.jsx
│   │   │       └── Toast.jsx
│   │   ├── contexts/
│   │   │   └── ToastContext.jsx  # ToastProvider and useToast hook
│   │   ├── services/
│   │   │   └── api.js
│   │   ├── utils/
│   │   │   └── auth.js           # Token storage and isAuthenticated helpers
│   │   ├── App.jsx               # Root router with ProtectedRoute guard
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── postcss.config.js
├── .env.example
├── render.yaml
├── .gitignore
├── README.md
└── plan.md (this file)
```

---

## Verification Steps

### Automated Testing

1. **Unit Tests** — Test each scraper individually with mock responses
2. **Integration Tests** — Test API endpoints with test database
3. **E2E Tests** — Use Playwright to test complete user flows

### Manual Verification

1. **Scraper Accuracy** — Add 3-5 real tracking numbers for each carrier, verify data matches official tracking pages
2. **Auto-Refresh** — Add undelivered tracking, wait 3 hours, verify automatic update
3. **Auto-Cleanup** — Mark tracking as delivered, wait 3 days, verify deletion
4. **Multi-User Isolation** — Create 2 accounts, verify users cannot see each other's data
5. **Performance** — Add 20+ tracking numbers, verify page loads in <2 seconds
6. **Mobile Responsiveness** — Test on iPhone and Android devices
7. **Error Resilience** — Disconnect internet, verify graceful error messages
8. **Rate Limiting** — Submit 15 requests rapidly, verify throttling
9. **Cold Start** — Wait 15+ minutes (Render sleep), verify wake-up time <30 seconds
10. **Memory Usage** — Monitor Render metrics, ensure usage stays <400MB

---

## Decisions & Assumptions

### Technology Choices

- **Python FastAPI over Node.js** — Better async support for web scraping, smaller memory footprint for Render free tier
- **PostgreSQL over SQLite** — Better for multi-user concurrent access, Render free tier available
- **Playwright over Selenium** — Modern, faster, better stealth mode, handles JavaScript-heavy sites
- **React over Vue/Svelte** — Larger ecosystem, more resources for troubleshooting
- **JWT over session-based auth** — Stateless, no persistent session storage needed for Render free tier

### Scraping Strategy

- **Browser automation over direct HTTP** — Tracking sites use heavy JavaScript, no public APIs available
- **Sequential requests per carrier over full parallelization** — Prevents rate limiting and IP blocks
- **Retry with exponential backoff over immediate failure** — Network issues are common
- **Store raw JSON data** — Allows re-parsing if data structure changes without re-scraping

### Data Retention

- **3-day auto-delete after delivery** — Balances user convenience (checking recent deliveries) with database storage limits
- **Soft delete approach** — Allows recovery if user requests it before permanent cleanup
- **No historical analytics** — Keeps database small for free tier, focus on real-time tracking only

### Deployment

- **Render free tier** — Acceptable 15-min sleep tradeoff for zero cost
- **Single region deployment** — Free tier limitation, acceptable latency for North American users
- **No CDN** — Frontend is small, Render provides adequate performance

### Security

- **24-hour JWT expiration** — Balances convenience (don't require daily login) with security
- **Bcrypt password hashing** — Industry standard, good security/performance balance
- **No email verification** — Simplifies implementation, acceptable for internal business tool
- **Rate limiting 10/min** — Prevents abuse while allowing normal usage

---

## Further Considerations

### Potential Challenges

1. **Anti-Bot Detection** — If carriers update bot protection:
   - **Fallback**: Implement CAPTCHA solving (paid service like 2Captcha)
   - **Alternative**: Use residential proxy rotation (paid service)
   - **Mitigation**: Keep user-agent and stealth tactics updated

2. **Scheduler Missed Jobs on Render Free Tier** — Service sleeps after 15 min inactivity, stopping the scheduler:
   - **Recommended fix**: Set up a free external cron ping (cron-job.org) to call the `/api/admin/jobs/trigger-refresh` endpoint every 3 hours — this also keeps the service awake
   - **Alternative**: Trigger stale-data refresh on the `/list` endpoint when user opens the dashboard (piggyback on user activity)

3. **Rate Limiting on Free Tier** — If traffic grows:
   - **Option A**: Upgrade to Render paid tier ($7/month)
   - **Option B**: More aggressive caching (reduce scraping frequency)
   - **Option C**: Migrate to self-hosted VPS

4. **Site Structure Changes** — When carrier sites update:
   - **Solution**: Implement scraper health checks (daily automated test)
   - **Notification**: Email alert when scraper fails repeatedly
   - **Fix**: Update selectors in affected scraper file

### Future Enhancements (Out of Scope)

- Email notifications when package is delivered
- SMS alerts for delivery exceptions
- Mobile app (React Native)
- CSV export of tracking history
- Advanced analytics dashboard
- Webhook support for external integrations
- Support for additional carriers (USPS, Canpar, Purolator, etc.)
- **Carrier auto-detection** — UPS numbers start with `1Z`, FedEx with 12/15/20 digits. Could auto-select carrier when user pastes a tracking number, removing a manual step. Implement as a `detectCarrier(trackingNumber)` utility in `src/utils/auth.js`.
- **Bulk import from CSV** — Allow users to upload a CSV file with tracking numbers instead of pasting them line by line.

### Performance Optimization (If Needed)

- Implement Redis caching layer (requires paid add-on on Render)
- Switch to serverless functions for scraping (AWS Lambda)
- Use separate microservice for scraping (isolate from main API)
- Implement WebSocket for real-time updates instead of polling

---

## Timeline Estimate

- **Phase 1-2 (Setup & Database)**: 4-6 hours
- **Phase 3 (Authentication)**: 3-4 hours
- **Phase 4 (Scraping)**: 8-12 hours ← Most complex
- **Phase 5-6 (API & Jobs)**: 4-6 hours
- **Phase 7 (Frontend)**: 10-14 hours ← Largest scope
- **Phase 8 (Error Handling)**: 3-4 hours
- **Phase 9 (Deployment)**: 3-4 hours
- **Phase 10 (Testing)**: 4-6 hours

**Total: 39-56 hours** of focused development time

### Recommended Workflow

1. **Work sequentially through phases** — Complete one phase fully before moving to next
2. **Test scrapers individually** — Ensure each carrier works before integration
3. **Deploy early** — After Phase 6, deploy to catch deployment issues before heavy frontend work
4. **Iterate on UI** — Frontend can be refined after initial deployment

---

## Getting Started

### .gitignore

Create `.gitignore` in the project root before first commit:

```
# Environment files — NEVER commit these
.env
.env.local
backend/.env

# Python
__pycache__/
*.py[cod]
venv/
.venv/
*.egg-info/
dist/
build/

# Playwright
/backend/test-results/
/backend/playwright-report/

# Node
node_modules/
frontend/dist/
frontend/.env
frontend/.env.local

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Alembic compiled
*.pyc
```

### Quick Start Commands

```bash
# Clone repository (replace with your repo URL)
git clone https://github.com/your-username/shipment-tracker.git
cd shipment-tracker

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Configure environment
cp .env.example .env
# Edit .env with your database URL and secret key

# Run database migrations
alembic upgrade head

# Start backend server
uvicorn app.main:app --reload

# Frontend setup (in new terminal)
cd frontend
npm install
npm run dev

# Access at http://localhost:5173
```

---

## Support & Troubleshooting

### Common Issues

**Issue: Playwright browser fails to launch**

- Solution: Install system dependencies: `playwright install-deps`

**Issue: Database connection fails**

- Solution: Verify DATABASE_URL is correct, ensure PostgreSQL is running

**Issue: CORS errors in browser**

- Solution: Check FRONTEND_URL in backend environment variables

**Issue: Scraper returns errors**

- Solution: Test tracking number on carrier's official website first, check for anti-bot detection

**Issue: Render service won't start**

- Solution: Check logs in Render dashboard, verify environment variables are set

### Logging

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("This is an info message")
logger.error("This is an error message", exc_info=True)
```

---

## Conclusion

This plan provides a complete roadmap for building a professional multi-carrier shipment tracking system. Follow the phases sequentially, test thoroughly, and iterate based on feedback. The system is designed to be scalable, maintainable, and cost-effective for business use.

**Good luck with your implementation! 🚀📦**
