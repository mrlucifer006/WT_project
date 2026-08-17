# User Guide: Event Ticketing & Verification System

This guide outlines how to use and host the Event Ticketing System across **GitHub Pages** (Frontend) and **Render** (Backend).

---

## 1. System Overview

The system is split into two components:
1. **Frontend (`frontend/`)**: Static web interface hosted on GitHub Pages (`https://<username>.github.io/<repo>/frontend/` or root).
2. **Backend (`backend/`)**: FastAPI Python server hosted on Render (`https://<your-render-app>.onrender.com`) handling WhatsApp automation, QR generation, token cryptography, and CSV transactions.

---

## 2. Step-by-Step Hosting Guide

### A. Hosting the Backend on Render

1. **Create an Account / Log In**: Go to [Render](https://render.com) and log in.
2. **Create a New Web Service**:
   - Click **New +** -> **Web Service**.
   - Connect your GitHub repository.
3. **Configure Service Settings**:
   - **Name**: e.g., `event-ticketing-backend`
   - **Root Directory**: `backend` *(Important!)*
   - **Environment**: `Python 3`
   - **Region**: Choose the closest region (e.g., Singapore, Frankfurt, Oregon).
   - **Branch**: `main` (or your active working branch).
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
4. **Set Environment Variables**:
   Under the **Environment Variables** section in Render, add:
   - `ADMIN_ID` (or `ADMIN_USERNAME`): Admin login ID (e.g., `admin`).
   - `ADMIN_PASSWORD`: Admin login password (e.g., `adminpassword`).
   - `ADMIN_PHONE`: Your WhatsApp phone number with country code (e.g., `919876543210`).
   - `WHATSAPP_SESSION_NAME`: `my_session`
   - `WARNING_BUFFER_MINUTES`: `5`
5. **Deploy**:
   - Click **Create Web Service**.
   - Once deployed, copy your Render application URL (e.g., `https://event-ticketing-backend.onrender.com`).

---

### B. Configuring the Frontend with Backend URL

Before deploying the frontend to GitHub Pages:
1. Open [`frontend/config.js`](file:///f:/5th_semester/WD/Billing/frontend/config.js).
2. Update `BACKEND_URL` with your Render backend URL:
   ```javascript
   const BACKEND_URL = "https://event-ticketing-backend.onrender.com";
   ```
3. Commit and push this change to GitHub:
   ```bash
   git add frontend/config.js
   git commit -m "Update BACKEND_URL for Render deployment"
   git push origin main
   ```

---

### C. Hosting the Frontend on GitHub Pages

There are two easy methods:

#### Method 1: Using GitHub Pages settings with `/frontend` (Recommended via GitHub Actions)
1. Go to your GitHub repository on [github.com](https://github.com).
2. Click **Settings** -> **Pages** (in the left sidebar).
3. Under **Build and deployment**:
   - **Source**: Select **GitHub Actions** or **Deploy from a branch**.
   - If using **Deploy from a branch**:
     - Choose `main` branch and `/ (root)` folder (or deploy the `frontend` folder using `gh-pages` branch).
4. *(Optional & Recommended)* To publish only the `frontend` folder as the root of GitHub Pages:
   Run these Git commands locally:
   ```bash
   git subtree push --prefix frontend origin gh-pages
   ```
   Then in GitHub Repository **Settings** -> **Pages**:
   - **Source**: Deploy from a branch
   - **Branch**: `gh-pages` -> `/ (root)`
   - Click **Save**.

Your frontend will be accessible at: `https://<username>.github.io/<repository-name>/`

---

## 3. Using the Application

### 1. WhatsApp Authentication
- When you first visit the frontend, if WhatsApp is not connected, a **WhatsApp Login Modal** will pop up with a QR code.
- Open WhatsApp on your phone -> **Linked Devices** -> **Link a Device** -> Scan the QR code on the webpage.
- Once connected, the modal automatically closes.

### 2. Issuing Entry Passes
- Fill in Participant Name, WhatsApp Phone Number, Pass Category (General Entry, VIP, Guest, Staff, etc.), and Duration.
- Click **Generate Entry Pass**.
- The participant immediately receives their unique encrypted QR pass on WhatsApp with entry confirmation.

### 3. Verifying QR & Starting Timers
- Admin scans the participant's QR pass.
- Admin starts the session timer. WhatsApp alerts are automatically sent when the session starts, at the 5-minute warning, and at session completion.

### 4. Attendance Dashboard & CSV Download
- Visit `data.html` or `participants.html` on your frontend.
- View real-time attendee counts and click **Download CSV** to export the full attendance records directly from the backend.
