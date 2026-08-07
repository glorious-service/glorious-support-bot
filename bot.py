import os
import logging
import json
import hashlib
import hmac
import re
import asyncio
import sys
import tempfile
import requests
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8769572062:AAHUV1IgodFFmZddZE-AjdlH4OeC_GSk4S0')

# Company information
COMPANY_NAME = "Glorious PLC"
COMPANY_PHONE = "+251906318888"
COMPANY_EMAIL = "social@glorious-plc.com"
COMPANY_SHORTCODE = "6331"
COMPANY_WEBSITE = "www.glorious-plc.com"
WORKING_HOURS = "Mon-Sat: 9:00 AM - 4:00 PM"

# Guarantee period (in days)
GUARANTEE_DAYS = 365

# ==================== PAYMENT CONFIGURATION ====================
BANK_NAME = "Commercial Bank of Ethiopia"
BANK_ACCOUNT_NAME = "Glorious PLC"
BANK_ACCOUNT_NUMBER = "1000123456789"
BANK_BRANCH = "Head Office"

TELEBIRR_SHORTCODE = "6331"
TELEBIRR_MERCHANT_ID = "GLORIOUSPLC"
TELEBIRR_PHONE = "+251906318888"

# ==================== API CONFIGURATION ====================
TELEBIRR_API_URL = "https://api.telebirr.et/v1"
TELEBIRR_API_KEY = "your_telebirr_api_key_here"
TELEBIRR_API_SECRET = "your_telebirr_api_secret_here"

CBE_API_URL = "https://api.cbe.et/v1"
CBE_API_KEY = "your_cbe_api_key_here"
CBE_API_SECRET = "your_cbe_api_secret_here"

BASE_SERVICE_FEE = 350

# ==================== GLOBAL VARIABLES ====================
# Setup directories based on environment
if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER') or os.environ.get('VERCEL'):
    SCREENSHOTS_DIR = os.path.join(tempfile.gettempdir(), 'payment_screenshots')
else:
    SCREENSHOTS_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "payment_screenshots")

# Create directory if it doesn't exist
if not os.path.exists(SCREENSHOTS_DIR):
    try:
        os.makedirs(SCREENSHOTS_DIR, mode=0o777)
        print(f"📁 Created screenshots directory: {SCREENSHOTS_DIR}")
    except Exception as e:
        print(f"⚠️ Could not create directory: {e}")
        SCREENSHOTS_DIR = os.path.join(os.getcwd(), "payment_screenshots")
        if not os.path.exists(SCREENSHOTS_DIR):
            os.makedirs(SCREENSHOTS_DIR, mode=0o777)

# ==================== ASYNCIO LOCK ====================
ticket_lock = asyncio.Lock()

# ==================== TICKET STORAGE ====================
if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER') or os.environ.get('VERCEL'):
    TICKETS_FILE = os.path.join(tempfile.gettempdir(), "tickets.json")
    REMINDERS_FILE = os.path.join(tempfile.gettempdir(), "reminders.json")
    RATINGS_FILE = os.path.join(tempfile.gettempdir(), "ratings.json")
    VISITS_FILE = os.path.join(tempfile.gettempdir(), "visits.json")
else:
    TICKETS_FILE = "tickets.json"
    REMINDERS_FILE = "reminders.json"
    RATINGS_FILE = "ratings.json"
    VISITS_FILE = "visits.json"

# ==================== DATA ====================
PRODUCT_CATEGORIES = {
    "televisions": {
        "name": "📺 Televisions",
        "name_am": "📺 ቴሌቪዥኖች",
        "brands": [
            {"id": "sony", "name": "📺 Sony Tv", "name_am": "📺 ሶኒ ቲቪ"},
            {"id": "hisense_tv", "name": "📺 Hisense TV", "name_am": "📺 ሃይሴንስ ቲቪ"},
            {"id": "other_tv", "name": "Other TV Brand", "name_am": "ሌላ የቲቪ ብራንድ"}
        ]
    },
    "refrigerators": {
        "name": "❄️ Refrigerators",
        "name_am": "❄️ ማቀዝቀዣዎች",
        "brands": [
            {"id": "hisense_fridge", "name": "Hisense", "name_am": "ሃይሴንስ"},
            {"id": "hitachi_fridge", "name": "Hitachi", "name_am": "ሂታቺ"},
            {"id": "other_fridge", "name": "Other Refrigerator Brand", "name_am": "ሌላ የማቀዝቀዣ ብራንድ"}
        ]
    },
    "stoves": {
        "name": "🔥 Stoves & Cooktops",
        "name_am": "🔥 ምድጃዎች",
        "brands": [
            {"id": "kumtel_stove", "name": "Kumtel", "name_am": "ኩምቴል"},
            {"id": "indesit_stove", "name": "InDesit", "name_am": "ኢንዴሲት"},
            {"id": "whirlpool_stove", "name": "Whirlpool", "name_am": "ዊርልፑል"},
            {"id": "other_stove", "name": "Other Stove Brand", "name_am": "ሌላ የምድጃ ብራንድ"}
        ]
    },
    "microwaves": {
        "name": "♨️ Microwaves",
        "name_am": "♨️ ማይክሮዌቭ",
        "brands": [
            {"id": "galanze_microwave", "name": "Galanze", "name_am": "ጋላንዜ"},
            {"id": "other_microwave", "name": "Other Microwave Brand", "name_am": "ሌላ የማይክሮዌቭ ብራንድ"}
        ]
    },
    "water_dispensers": {
        "name": "💧 Water Dispensers",
        "name_am": "💧 የውሃ ማከፋፈያ",
        "brands": [
            {"id": "midea_water", "name": "Midea", "name_am": "ሚዲያ"},
            {"id": "other_water", "name": "Other Water Dispenser Brand", "name_am": "ሌላ የውሃ ማከፋፈያ ብራንድ"}
        ]
    },
    "blenders": {
        "name": "🥤 Blenders & Mixers",
        "name_am": "🥤 ብሌንደሮች",
        "brands": [
            {"id": "philips_blender", "name": "Philips", "name_am": "ፊሊፕስ"},
            {"id": "moulinex_blender", "name": "Moulinex", "name_am": "ሙሊኔክስ"},
            {"id": "other_blender", "name": "Other Blender Brand", "name_am": "ሌላ የብሌንደር ብራንድ"}
        ]
    },
    "washing_machines": {
        "name": "👕 Washing Machines",
        "name_am": "👕 የልብስ ማጠቢያ",
        "brands": [
            {"id": "technix_washer", "name": "TechNix", "name_am": "ቴክኒክስ"},
            {"id": "hitachi_washer", "name": "Hitachi", "name_am": "ሂታቺ"},
            {"id": "hisense_washer", "name": "Hisense", "name_am": "ሃይሴንስ"},
            {"id": "aristone_washer", "name": "Aristone", "name_am": "አሪስቶን"},
            {"id": "other_washer", "name": "Other Washing Machine Brand", "name_am": "ሌላ የልብስ ማጠቢያ ብራንድ"}
        ]
    },
    "vacuum_cleaners": {
        "name": "🧹 Vacuum Cleaners",
        "name_am": "🧹 ቫኩም ክሊነሮች",
        "brands": [
            {"id": "philips_vacuum", "name": "Philips", "name_am": "ፊሊፕስ"},
            {"id": "hitachi_vacuum", "name": "Hitachi", "name_am": "ሂታቺ"},
            {"id": "other_vacuum", "name": "Other Vacuum Brand", "name_am": "ሌላ የቫኩም ብራንድ"}
        ]
    },
    "food_processors": {
        "name": "🍳 Food Processors",
        "name_am": "🍳 የምግብ ማቀነባበሪያ",
        "brands": [
            {"id": "philips_processor", "name": "Philips", "name_am": "ፊሊፕስ"},
            {"id": "moulinex_processor", "name": "Moulinex", "name_am": "ሙሊኔክስ"},
            {"id": "other_processor", "name": "Other Food Processor Brand", "name_am": "ሌላ የምግብ ማቀነባበሪያ ብራንድ"}
        ]
    },
    "soundbars": {
        "name": "🔊 Sound Bars",
        "name_am": "🔊 ሳውንድ ባር",
        "brands": [
            {"id": "sony_soundbar", "name": "Sony", "name_am": "ሶኒ"},
            {"id": "other_soundbar", "name": "Other Sound Bar Brand", "name_am": "ሌላ የሳውንድ ባር ብራንድ"}
        ]
    },
    "other_appliances": {
        "name": "🏠 Other Appliances",
        "name_am": "🏠 ሌሎች መገልገያዎች",
        "brands": [
            {"id": "iron", "name": "Iron", "name_am": "ብረት"},
            {"id": "heater", "name": "Heater", "name_am": "ማሞቂያ"},
            {"id": "fan", "name": "Fan", "name_am": "ማራገቢያ"},
            {"id": "humidity", "name": "Humidifier", "name_am": "እርጥበት ማስተካከያ"},
            {"id": "other_home", "name": "Other Home Appliance", "name_am": "ሌላ የቤት መገልገያ"}
        ]
    }
}

ISSUE_TYPES = [
    {"id": "installation", "name": "🔧 Installation Help", "name_am": "🔧 የመጫኛ እርዳታ"},
    {"id": "warranty", "name": "📋 Warranty Query", "name_am": "📋 የዋስትና ጥያቄ"},
    {"id": "repair", "name": "🔨 Repair Needed", "name_am": "🔨 ጥገና ያስፈልጋል"},
    {"id": "parts", "name": "🔄 Replacement Parts", "name_am": "🔄 መለዋወጫ ክፍሎች"},
    {"id": "manual", "name": "📖 Need Manual/Guide", "name_am": "📖 መመሪያ ያስፈልጋል"},
    {"id": "other_issue", "name": "❓ Other Issue", "name_am": "❓ ሌላ ችግር"}
]

# Store user sessions
user_sessions = {}

# ==================== ADMIN USER IDS ====================
ADMIN_USER_IDS = [
    6753172050,  # ← PUT YOUR TELEGRAM ID HERE!
]

# ==================== CONVERSATION STATES ====================
(
    SELECTING_CATEGORY,
    SELECTING_BRAND,
    SELECTING_ISSUE,
    SELECTING_SERVICE_TYPE,
    DESCRIBING_ISSUE,
    ASKING_NAME,
    ASKING_PHONE,
    ASKING_LOCATION,
    SELECTING_LANGUAGE,
    PAYMENT_METHOD,
    PAYMENT_VERIFICATION,
    PROVIDING_QUOTE,
    SCREENSHOT_UPLOAD,
    RATING_SERVICE,
    SCHEDULING_APPOINTMENT,
    SEARCH_TICKETS,
    SCHEDULING_TECHNICIAN,
    TECHNICIAN_VERIFICATION,
    WAITING_FOR_PAYMENT_REFERENCE,
    PROVIDING_SUGGESTION
) = range(20)

# ==================== TICKET MANAGER ====================

class TicketManager:
    def __init__(self):
        self.tickets = {}
        self.counter = 2026001
        self.reminders = {}
        self.ratings = {}
        self.visits = {}
        self.load_tickets()
        self.load_reminders()
        self.load_ratings()
        self.load_visits()
    
    def generate_ticket_id(self):
        ticket_id = f"GLR-{datetime.now().year}-{self.counter:06d}"
        self.counter += 1
        return ticket_id
    
    def create_ticket(self, user_id, data):
        ticket_id = self.generate_ticket_id()
        ticket = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "user_name": data.get("user_name", ""),
            "username": data.get("username", ""),
            "phone": data.get("phone", ""),
            "location": data.get("location", ""),
            "location_lat": data.get("location_lat", ""),
            "location_lon": data.get("location_lon", ""),
            "location_link": data.get("location_link", ""),
            "category": data.get("category", ""),
            "category_name": data.get("category_name", ""),
            "brand": data.get("brand", ""),
            "brand_name": data.get("brand_name", ""),
            "issue_type": data.get("issue_type", ""),
            "issue_name": data.get("issue_name", ""),
            "service_type": data.get("service_type", "technician"),
            "description": data.get("description", ""),
            "suggestion": "",
            "status": "Pending Review",
            "payment_status": "Not Required",
            "payment_amount": 0,
            "payment_method": "",
            "payment_reference": "",
            "payment_verified": False,
            "payment_verification_data": "",
            "quote_materials": "",
            "quote_material_cost": 0,
            "quote_service_fee": 0,
            "quote_total": 0,
            "quote_provided": False,
            "assigned_to": "",
            "estimated_visit": "",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "completed_at": "",
            "guarantee_expiry": "",
            "language": data.get("language", "en"),
            "technician_verification": {
                "status": "pending",
                "technician_name": "",
                "technician_phone": "",
                "visit_date": "",
                "visit_time": "",
                "findings": "",
                "verified_issue": "",
                "confirmed": False,
                "confirmation_date": ""
            },
            "chat_history": [],
            "preferred_contact": "telegram",
            "appointment_preference": "any",
            "scheduled_date": "",
            "scheduled_time": "",
            "rating": None,
            "rating_comment": "",
            "rating_date": "",
            "reminders_sent": [],
            "last_reminder": ""
        }
        self.tickets[ticket_id] = ticket
        self.save_tickets()
        return ticket
    
    def get_ticket(self, ticket_id):
        return self.tickets.get(ticket_id)
    
    def update_status(self, ticket_id, status):
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["status"] = status
            self.tickets[ticket_id]["updated_at"] = datetime.now().isoformat()
            if status == "Completed":
                self.tickets[ticket_id]["completed_at"] = datetime.now().isoformat()
                self.tickets[ticket_id]["guarantee_expiry"] = (datetime.now() + timedelta(days=GUARANTEE_DAYS)).isoformat()
            self.save_tickets()
            return True
        return False
    
    def schedule_technician_visit(self, ticket_id, technician_name, technician_phone, visit_date, visit_time):
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["technician_verification"]["status"] = "scheduled"
            self.tickets[ticket_id]["technician_verification"]["technician_name"] = technician_name
            self.tickets[ticket_id]["technician_verification"]["technician_phone"] = technician_phone
            self.tickets[ticket_id]["technician_verification"]["visit_date"] = visit_date
            self.tickets[ticket_id]["technician_verification"]["visit_time"] = visit_time
            self.tickets[ticket_id]["status"] = "Technician Scheduled"
            self.tickets[ticket_id]["updated_at"] = datetime.now().isoformat()
            self.save_tickets()
            return True
        return False
    
    def confirm_technician_verification(self, ticket_id, findings, verified_issue, materials="", material_cost=0, service_fee=BASE_SERVICE_FEE):
        if ticket_id in self.tickets:
            ticket = self.tickets[ticket_id]
            ticket["technician_verification"]["status"] = "completed"
            ticket["technician_verification"]["findings"] = findings
            ticket["technician_verification"]["verified_issue"] = verified_issue
            ticket["technician_verification"]["confirmed"] = True
            ticket["technician_verification"]["confirmation_date"] = datetime.now().isoformat()
            
            total = material_cost + service_fee
            ticket["quote_materials"] = materials
            ticket["quote_material_cost"] = material_cost
            ticket["quote_service_fee"] = service_fee
            ticket["quote_total"] = total
            ticket["quote_provided"] = True
            ticket["suggestion"] = verified_issue
            
            if material_cost == 0 and service_fee == 0:
                ticket["payment_status"] = "Not Required"
                ticket["payment_amount"] = 0
                ticket["status"] = "Suggestion Provided"
            else:
                ticket["payment_status"] = "Pending"
                ticket["payment_amount"] = total
                ticket["status"] = "Awaiting Payment"
            
            ticket["updated_at"] = datetime.now().isoformat()
            self.save_tickets()
            return True
        return False
    
    def provide_suggestion(self, ticket_id, suggestion):
        """Provide a suggestion without requiring technician visit"""
        if ticket_id in self.tickets:
            ticket = self.tickets[ticket_id]
            ticket["suggestion"] = suggestion
            ticket["quote_provided"] = True
            ticket["payment_status"] = "Not Required"
            ticket["payment_amount"] = 0
            ticket["status"] = "Suggestion Provided"
            ticket["updated_at"] = datetime.now().isoformat()
            self.save_tickets()
            return True
        return False
    
    def update_payment(self, ticket_id, payment_method, payment_reference, amount, verified=False, verification_data=""):
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["payment_status"] = "Paid" if verified else "Pending Verification"
            self.tickets[ticket_id]["payment_method"] = payment_method
            self.tickets[ticket_id]["payment_reference"] = payment_reference
            self.tickets[ticket_id]["payment_amount"] = amount
            self.tickets[ticket_id]["payment_verified"] = verified
            self.tickets[ticket_id]["payment_verification_data"] = verification_data
            self.tickets[ticket_id]["status"] = "Payment Confirmed" if verified else "Awaiting Verification"
            self.tickets[ticket_id]["updated_at"] = datetime.now().isoformat()
            self.save_tickets()
            return True
        return False
    
    def verify_payment(self, ticket_id, verified, verification_data=""):
        if ticket_id in self.tickets:
            ticket = self.tickets[ticket_id]
            
            ticket["payment_verified"] = verified
            ticket["payment_verification_data"] = verification_data
            
            if verified:
                ticket["payment_status"] = "Paid"
                ticket["status"] = "Payment Confirmed"
            else:
                ticket["payment_status"] = "Verification Failed"
                ticket["status"] = "Payment Failed"
            
            ticket["updated_at"] = datetime.now().isoformat()
            self.save_tickets()
            return True
        return False
    
    def add_rating(self, ticket_id, rating, comment=""):
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["rating"] = rating
            self.tickets[ticket_id]["rating_comment"] = comment
            self.tickets[ticket_id]["rating_date"] = datetime.now().isoformat()
            self.tickets[ticket_id]["updated_at"] = datetime.now().isoformat()
            self.save_tickets()
            return True
        return False
    
    def get_pending_technician_visits(self):
        return [t for t in self.tickets.values() if t.get("technician_verification", {}).get("status") == "pending"]
    
    def get_scheduled_visits(self):
        return [t for t in self.tickets.values() if t.get("technician_verification", {}).get("status") == "scheduled"]
    
    def get_tickets_awaiting_quote(self):
        return [t for t in self.tickets.values() if t.get("status") == "Pending Review"]
    
    def get_tickets_by_status(self, status):
        return [t for t in self.tickets.values() if t.get("status") == status]
    
    def get_tickets_awaiting_rating(self):
        return [t for t in self.tickets.values() if t.get("status") == "Completed" and t.get("rating") is None]
    
    def search_tickets(self, query):
        query = query.lower()
        results = []
        for ticket in self.tickets.values():
            if (query in ticket.get("ticket_id", "").lower() or
                query in ticket.get("user_name", "").lower() or
                query in ticket.get("phone", "").lower() or
                query in ticket.get("category_name", "").lower() or
                query in ticket.get("brand_name", "").lower() or
                query in ticket.get("issue_name", "").lower() or
                query in ticket.get("description", "").lower()):
                results.append(ticket)
        return results
    
    def get_statistics(self):
        all_tickets = self.get_all_tickets()
        total = len(all_tickets)
        pending_review = len(self.get_tickets_awaiting_quote())
        technician_pending = len(self.get_pending_technician_visits())
        technician_scheduled = len(self.get_scheduled_visits())
        pending_payment = len([t for t in all_tickets if t.get("status") == "Awaiting Payment"])
        pending_verification = len([t for t in all_tickets if t.get("status") == "Awaiting Verification"])
        payment_confirmed = len([t for t in all_tickets if t.get("status") == "Payment Confirmed"])
        in_progress = len([t for t in all_tickets if t.get("status") == "In Progress"])
        completed = len([t for t in all_tickets if t.get("status") == "Completed"])
        suggestion_provided = len([t for t in all_tickets if t.get("status") == "Suggestion Provided"])
        cancelled = len([t for t in all_tickets if t.get("status") == "Cancelled"])
        rated = len([t for t in all_tickets if t.get("rating") is not None])
        awaiting_rating = len(self.get_tickets_awaiting_rating())
        
        return {
            "total": total,
            "pending_review": pending_review,
            "technician_pending": technician_pending,
            "technician_scheduled": technician_scheduled,
            "pending_payment": pending_payment,
            "pending_verification": pending_verification,
            "payment_confirmed": payment_confirmed,
            "in_progress": in_progress,
            "completed": completed,
            "suggestion_provided": suggestion_provided,
            "cancelled": cancelled,
            "rated": rated,
            "awaiting_rating": awaiting_rating
        }
    
    def get_average_rating(self):
        rated = [t for t in self.tickets.values() if t.get("rating") is not None]
        if not rated:
            return 0
        return sum(t["rating"] for t in rated) / len(rated)
    
    def get_all_tickets(self):
        return list(self.tickets.values())
    
    def get_user_tickets(self, user_id):
        return [t for t in self.tickets.values() if t["user_id"] == user_id]
    
    def get_daily_tickets(self, date=None):
        if date is None:
            date = datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        return [t for t in self.tickets.values() if t.get("created_at", "").startswith(date_str)]
    
    def get_pending_payments(self):
        return [t for t in self.tickets.values() if t.get("payment_status") in ["Pending", "Pending Verification"]]
    
    def save_tickets(self):
        try:
            with open(TICKETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.tickets, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Tickets saved to {TICKETS_FILE}")
        except Exception as e:
            logger.error(f"❌ Failed to save tickets: {e}")
    
    def load_tickets(self):
        try:
            if os.path.exists(TICKETS_FILE):
                with open(TICKETS_FILE, 'r', encoding='utf-8') as f:
                    loaded_tickets = json.load(f)
                    self.tickets = loaded_tickets
                    logger.info(f"✅ Loaded {len(loaded_tickets)} tickets from {TICKETS_FILE}")
                    return True
        except Exception as e:
            logger.error(f"❌ Failed to load tickets: {e}")
        return False
    
    def load_reminders(self):
        try:
            if os.path.exists(REMINDERS_FILE):
                with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
                    self.reminders = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load reminders: {e}")
    
    def save_reminders(self):
        try:
            with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save reminders: {e}")
    
    def load_ratings(self):
        try:
            if os.path.exists(RATINGS_FILE):
                with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
                    self.ratings = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load ratings: {e}")
    
    def save_ratings(self):
        try:
            with open(RATINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.ratings, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save ratings: {e}")
    
    def load_visits(self):
        try:
            if os.path.exists(VISITS_FILE):
                with open(VISITS_FILE, 'r', encoding='utf-8') as f:
                    self.visits = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load visits: {e}")
    
    def save_visits(self):
        try:
            with open(VISITS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.visits, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save visits: {e}")

ticket_manager = TicketManager()

# ==================== LANGUAGE TRANSLATIONS ====================
LANGUAGES = {
    "en": {
        "name": "English",
        "flag": "🇬🇧",
        "welcome": "👋 *Welcome to {} Support!*\n\nThank you for choosing us for over 45 years! 🎉\n\nI'm here to help you with after-sales service for:\n• 📱 Electronics\n• 🍳 Kitchen Aids\n• 🏠 Home Appliances\n\nHow can I help you today?",
        "product_support": "🛠️ Product Support",
        "faq": "❓ FAQ",
        "contact": "📞 Contact Support",
        "about": "ℹ️ About Us",
        "my_tickets": "📋 My Tickets",
        "admin_panel": "📊 Admin Panel",
        "payment": "💳 Make Payment",
        "select_category": "🛒 *Select Product Category*\n\nPlease choose the category of your product:",
        "select_brand": "🏷️ *Select Brand*\n\nCategory: {}\n\nPlease select your product brand:",
        "select_issue": "🛠️ *Select Issue Type*\n\nWhat kind of support do you need?",
        "select_service_type": "🤔 *How would you like to proceed?*\n\nPlease choose how you want to handle this issue:\n\n💡 *Suggestion Only* - Get free advice/recommendation (No technician visit)\n🔧 *Technician Required* - A technician will visit to verify the issue in person\n\nWhich option do you prefer?",
        "service_type_suggestion": "💡 Suggestion Only",
        "service_type_technician": "🔧 Technician Required",
        "describe_issue": "📝 Please describe your issue in detail.\n\n*Category:* {}\n*Brand:* {}\n*Issue Type:* {}\n*Service Type:* {}\n\nPlease provide:\n• Product model\n• Purchase date (if known)\n• Detailed description of the problem\n\nType your message below:",
        "ask_name": "✅ Description received!\n\n📝 *Please enter your full name:*\n(This helps us identify you)",
        "ask_phone": "✅ Name: {}\n\n📱 *Please enter your phone number:*\n(Format: 09XXXXXXXX or +2519XXXXXXXX or 07XXXXXXXX OR +2517XXXXXXXX)",
        "ask_location": "✅ Phone: {}\n\n📍 *Would you like to share your location?*\nThis helps us provide faster service.\n\n📍 Press 'Share Location' to send your location\n⏭️ Press 'Skip Location' to skip",
        "share_location": "📍 Share Location",
        "skip_location": "Skip Location",
        "location_received": "✅ Location received!\n\n📍 {}",
        "ticket_created": "✅ *Your issue has been recorded!*\n\n🎫 *Ticket Number:* `{}`\n\n📋 *Summary:*\n• Customer: {}\n• Phone: {}\n• Location: {}\n• Product: {}\n• Brand: {}\n• Issue: {}\n• Service Type: {}\n\n⏳ *Next Step:* {}\n\nThank you for choosing Glorious PLC! 🙏",
        "check_ticket": "📋 Check Ticket Status",
        "back": "🔙 Back",
        "back_to_menu": "🔙 Back to Menu",
        "faq_text": "❓ *Frequently Asked Questions*\n\n🔹 *Warranty Period*\nAll products come with a minimum 1-year warranty.\n\n🔹 *Service Guarantee*\nAll repair work comes with a **1-year guarantee** on parts and labor.\nIf the same issue recurs within 1 year, we will fix it at **no additional cost**.\n\n🔹 *Service Options*\nYou can choose between:\n• 💡 *Suggestion Only* - Free advice without technician visit\n• 🔧 *Technician Required* - In-person verification before payment\n\n🔹 *Rating System*\nAfter your service is completed, you will be asked to rate your experience.\nYour feedback helps us improve our service! ⭐\n\n🔹 *How to claim warranty?*\nContact us through this bot or call our support line.\n\n🔹 *Service Centers*\nWe have service centers in all major cities.\n\n🔹 *Product Manuals*\nDigital manuals are available upon request.\n\nFor more detailed assistance, please use our Product Support option.",
        "contact_text": "📞 *Contact Support*\n\n📱 *Phone:* {}\n📧 *Email:* {}\n🕐 *Working Hours:* {}\n\n💡 *Quick Tip:* Use the Product Support option for faster resolution!",
        "about_text": "🏢 *About {}*\n\n✨ *Over 45 Years of Excellence!*\n\nWe have been serving customers since 1978, providing quality:\n📱 Electronics\n🍳 Kitchen Aids\n🏠 Home Appliances\n\n🎯 *Our Mission:*\nTo provide exceptional products and unmatched after-sales support.\n\n⭐ *Why Choose Us?*\n• 45+ years of experience\n• Trusted by thousands\n• Dedicated support team\n• Quality assured products\n• **1-year guarantee on all repairs**\n• **Pay only after technician verification**\n• **Rate your service experience**\n\nWe're here to help you!",
        "no_tickets": "📭 You have no tickets.\n\nUse the 'Product Support' button to create a ticket.",
        "your_tickets": "📋 *Your Tickets*\n\n",
        "ticket_status": "🔍 *Ticket Status*\n\n🎫 *Ticket:* `{}`\n{} *Status:* {}\n\n👤 *Customer:* {}\n📱 *Phone:* {}\n📍 *Location:* {}\n\n📱 *Product:* {}\n🏷️ *Brand:* {}\n🛠️ *Issue:* {}\n💡 *Service Type:* {}\n\n{}\n\n📅 *Created:* {}\n{}\n{}\n\n⭐ *Rating:* {}\n\n🔒 *Guarantee:* {}\n\n💡 *Next Steps:*\n{}\n",
        "all_tickets": "📋 *ALL SERVICE TICKETS*\n\n📊 Total: {} tickets\n\n",
        "admin_panel_text": "📊 *Admin Panel*\n\n📋 *Statistics:*\n• Total Tickets: {}\n• Today's Tickets ({}): {}\n• 📋 Pending Review: {}\n• 🔧 Technician Pending: {}\n• 🔧 Technician Scheduled: {}\n• 💰 Awaiting Payment: {}\n• 🔍 Awaiting Verification: {}\n• 💡 Suggestion Provided: {}\n• ✅ Completed: {}\n• ⭐ Rated: {}\n• 📝 Awaiting Rating: {}\n\n⭐ Average Rating: {:.1f} / 5.0\n\nSelect an option below:",
        "admin_all_tickets": "📊 All Tickets",
        "admin_export_all": "📊 Export All Tickets",
        "admin_export_daily": "📊 Export Today's Tickets ({})",
        "admin_pending_payments": "💰 Pending Payments",
        "admin_pending_review": "📋 Pending Review",
        "admin_pending_verification": "🔍 Pending Verification",
        "admin_technician_visits": "🔧 Technician Visits",
        "admin_provide_suggestion": "💡 Provide Suggestion",
        "admin_view_ratings": "⭐ View Ratings",
        "unauthorized": "❌ You are not authorized.",
        "no_tickets_found": "📭 No tickets found.",
        "no_tickets_to_export": "📭 No tickets to export.",
        "exporting": "⏳ Generating export file...",
        "export_complete": "✅ Export complete!",
        "export_caption_all": "📊 Complete Ticket Export\n📋 {} tickets exported\n📅 {}",
        "export_caption_daily": "📊 Daily Ticket Export\n📋 {} tickets from {}\n📅 {}",
        "no_daily_tickets": "📭 No tickets found for {}.",
        "processing": "✅ Processing...",
        "location_reminder": "📍 Please use the buttons below to share your location or skip:\n\n📍 Press 'Share Location' to send your location\n⏭️ Press 'Skip Location' to skip",
        "default_message": "🤔 I'm not sure what you need. Please use the menu buttons below.",
        "select_language": "🌐 *Select Your Language / ቋንቋዎን ይምረጡ*\n\nPlease select your preferred language:\nእባክዎ የሚመርጡትን ቋንቋ ይምረጡ:",
        "language_changed": "✅ Language changed to {}! / ቋንቋ ወደ {} ተቀየረ!",
        "change_language": "🌐 Change Language / ቋንቋ ቀይር",
        "no_ticket_found": "❌ Ticket {} not found.",
        "location_not_shared": "Not shared",
        "location_not_provided": "Not provided",
        "shared_location": "📍 Shared",
        "view_on_map": "📍 View on Map",
        "assigned_to": "👨‍🔧 *Assigned To:* {}",
        "estimated_visit": "📅 *Estimated Visit:* {}",
        "guarantee_info": "🔒 *1-Year Guarantee*\nThis repair is covered for 1 year from completion.",
        "guarantee_expiry": "🔒 *Guarantee expires:* {}",
        "guarantee_active": "✅ Active",
        "guarantee_expired": "❌ Expired",
        "status_pending_review": "📋",
        "status_technician_scheduled": "🔧",
        "status_awaiting_payment": "💰",
        "status_awaiting_verification": "🔍",
        "status_payment_confirmed": "✅",
        "status_in_progress": "🔄",
        "status_completed": "✅",
        "status_suggestion_provided": "💡",
        "status_cancelled": "❌",
        "status_default": "📌",
        "name_too_short": "❌ Please enter your full name (at least 2 characters):",
        "phone_invalid": "❌ Please enter a valid phone number (at least 10 digits):",
        "payment_options": "💳 *Payment Options*\n\nPlease choose your payment method:\n\n💵 *Total Amount:* {} ETB\n\nSelect payment method below:",
        "payment_telebirr": "📱 Tele Birr",
        "payment_bank": "🏦 Bank Transfer",
        "payment_telebirr_info": "📱 *Tele Birr Payment*\n\n📌 *Amount:* {} ETB\n📌 *Shortcode:* {}\n📌 *Merchant:* {}\n📌 *Reference:* `{}`\n\n📱 *Steps:*\n1. Open Tele Birr App\n2. Select 'Pay to Merchant'\n3. Enter Shortcode: `{}`\n4. Enter Amount: `{}` ETB\n5. Enter Reference: `{}`\n6. Confirm payment\n\n📱 *Tele Birr Support:* {}\n\n✅ Your payment will be automatically verified.",
        "payment_bank_info": "🏦 *Bank Transfer Details*\n\n🏦 *Bank:* {}\n📌 *Account Name:* {}\n📌 *Account Number:* `{}`\n📌 *Branch:* {}\n💵 *Amount:* {} ETB\n📝 *Reference:* `{}`\n\n📱 *Phone:* {}\n\n✅ Your payment will be automatically verified.",
        "payment_confirm": "✅ I have made the payment",
        "payment_confirmed": "✅ *Payment Confirmed!*\n\n🎫 *Ticket:* `{}`\n💰 *Amount:* {} ETB\n💳 *Method:* {}\n📝 *Reference:* {}\n\n⏳ Our technician will now be assigned to your service.\nWe will contact you within 24 hours.\n\n🔒 *1-Year Guarantee:* All repairs are covered for 1 year!\n\n⭐ *After service completion, you will be asked to rate your experience!*\n\nThank you for choosing Glorious PLC! 🙏",
        "payment_verification": "📋 *Payment Verification*\n\nPlease enter your transaction reference number:\n\n📱 *Tele Birr:* Enter transaction ID\n🏦 *Bank Transfer:* Enter reference number",
        "payment_verifying": "⏳ *Verifying your payment...*\n\nPlease wait while we confirm your payment.",
        "payment_verified": "✅ *Payment Verified Successfully!*\n\n🎫 *Ticket:* `{}`\n💰 *Amount:* {} ETB\n\nYour payment has been confirmed. We will now proceed with your service.\n\n🔒 *1-Year Guarantee:* All repairs are covered for 1 year!\n\n⭐ *After service completion, you will be asked to rate your experience!*",
        "payment_failed": "❌ *Payment Verification Failed*\n\nWe could not verify your payment. Please check:\n• The reference number is correct\n• The amount matches\n• The payment was completed\n\nIf you continue to have issues, please contact support.",
        "payment_pending": "⏳ Pending Payment",
        "payment_paid": "✅ Paid",
        "payment_verification_failed": "❌ Verification Failed",
        "confirm_payment": "✅ Confirm Payment",
        "pending_payments_list": "💰 *Pending Payments*\n\nTotal: {} pending payments\n\n",
        "no_pending_payments": "✅ No pending payments.",
        "pending_review_list": "📋 *Tickets Pending Review*\n\nTotal: {} tickets\n\n",
        "no_pending_review": "📭 No tickets pending review.",
        "provide_quote_instruction": "📝 *Provide Response for Ticket:* `{}`\n\n👤 Customer: {}\n📱 Phone: {}\n🛠️ Issue: {}\n💡 Service Type: {}\n\n---\n\n*How to write your response (any format works):*\n\n**1. Suggestion Only (Free Advice):**\n`The TV needs a software update. Please try resetting the system.`\n\n**2. Cost Only:**\n`Materials: Power supply board | Material Cost: 850 | Service Fee: 350`\n\n**3. Both Suggestion and Cost:**\n`The power supply board is faulty and needs replacement. Material Cost: 850, Service Fee: 350`\n\n**4. Simple Format:**\n`Power supply board needs replacement. Cost 850 birr, labor 350 birr`\n\n**5. Multi-line:**\n```\nSuggestion: The power supply board is faulty\nMaterials: Power supply board\nCost: 850 birr\nService Fee: 350 birr\n```\n\n---\n\n💡 *You can provide:*\n• Suggestion only (no cost)\n• Cost only (materials and fees)\n• Both suggestion and cost\n\nType your response below:",
        "quote_provided": "✅ *Response Provided Successfully!*\n\n🎫 Ticket: `{}`\n👤 Customer: {}\n\n{}\n\n{}\n\n{}\n\n✅ Response has been sent to the customer.",
        "quote_failed": "❌ Failed to provide response. Please check the format and try again.",
        "no_quote_ticket": "❌ Ticket not found.",
        "pending_verification_list": "🔍 *Pending Verification*\n\nTotal: {} payments waiting verification\n\n",
        "no_pending_verification": "✅ No payments waiting verification.",
        "admin_verify_payment": "✅ Verify Payment",
        "admin_reject_payment": "❌ Reject Payment",
        "payment_verified_admin": "✅ *Payment Verified by Admin*\n\n🎫 Ticket: {}\n💰 Amount: {} ETB\n💳 Method: {}\n📝 Reference: {}\n\nPayment has been confirmed.\n\n🔒 *1-Year Guarantee:* All repairs are covered for 1 year!",
        "payment_rejected_admin": "❌ *Payment Rejected*\n\n🎫 Ticket: {}\n\nPayment verification failed. Please check the payment details.",
        "rate_service": "⭐ *Rate Our Service*\n\nHow would you rate your experience?\n\n⭐ 1 - Very Poor\n⭐ 2 - Poor\n⭐ 3 - Average\n⭐ 4 - Good\n⭐ 5 - Excellent\n\nYour feedback helps us improve! 🙏",
        "rating_received": "✅ *Thank you for your rating!*\n\n⭐ Rating: {} / 5\n💬 Comment: {}\n\nWe appreciate your feedback! 🙏\n\nYour rating helps us serve you better!",
        "schedule_appointment": "📅 *Schedule Appointment*\n\nWhen would you like our technician to visit?\n\nPlease select a day:",
        "appointment_scheduled": "✅ *Appointment Scheduled!*\n\n📅 Date: {}\n⏰ Time: {}\n\nOur technician will visit you on the scheduled date.\n\n⭐ *After service completion, you will be asked to rate your experience!*",
        "reminder_set": "⏰ *Reminder Set*\n\nYou will receive a reminder 24 hours before your appointment.",
        "rating_options": "⭐ *Rate Your Experience*\n\nPlease rate your service experience:\n\n⭐ 1 - Very Poor\n⭐ 2 - Poor\n⭐ 3 - Average\n⭐ 4 - Good\n⭐ 5 - Excellent\n\nSelect your rating below:",
        "rate_1": "⭐ 1 Star - Very Poor",
        "rate_2": "⭐⭐ 2 Stars - Poor",
        "rate_3": "⭐⭐⭐ 3 Stars - Average",
        "rate_4": "⭐⭐⭐⭐ 4 Stars - Good",
        "rate_5": "⭐⭐⭐⭐⭐ 5 Stars - Excellent",
        "no_rating": "Not rated yet",
        "rating_comment_prompt": "📝 *Add a Comment (Optional)*\n\nYou can add a comment about your experience.\n\nType your comment below or press 'Skip' to finish:",
        "rating_skip": "⏭️ Skip Comment",
        "rating_comment_received": "✅ *Comment Received!*\n\nThank you for your detailed feedback! 🙏",
        "technician_verification": "🔧 *Technician Verification*\n\nOur technician needs to verify the issue in person before proceeding.\n\n📅 A visit will be scheduled to inspect your device.\n\n⏳ Please wait for a confirmation.",
        "technician_scheduled": "🔧 *Technician Scheduled!*\n\n📅 Date: {}\n⏰ Time: {}\n👨‍🔧 Technician: {}\n📱 Phone: {}\n\nOur technician will visit your location to verify the issue.\n\n⚠️ *Payment will only be required after verification.*",
        "technician_confirmation": "✅ *Technician Verification Complete!*\n\n🎫 Ticket: `{}`\n\n🔍 *Findings:*\n{}\n\n📋 *Verified Issue:*\n{}\n\n📦 *Materials Required:* {}\n💰 *Material Cost:* {} ETB\n🔧 *Service Fee:* {} ETB\n💵 *Total:* {} ETB\n\n💳 Please make payment to proceed with the service.\n\n⭐ *After service completion, you will be asked to rate your experience!*",
        "technician_note": "📝 *Technician Notes:*\n\n• Please ensure the device is accessible\n• Have your proof of purchase ready\n• The technician will inspect and verify the issue\n• Payment only after verification",
        "admin_schedule_visit": "🔧 *Schedule Technician Visit*\n\nFor Ticket: `{}`\n👤 Customer: {}\n📱 Phone: {}\n📍 Location: {}\n💡 Service Type: {}\n\nPlease provide:\n• Technician Name\n• Technician Phone\n• Visit Date (YYYY-MM-DD)\n• Visit Time\n\nFormat: `Name | Phone | Date | Time`\nExample: `John Smith | 0912345678 | 2024-01-15 | 10:00 AM`",
        "visit_scheduled": "✅ *Visit Scheduled!*\n\n🎫 Ticket: {}\n👨‍🔧 Technician: {}\n📅 Date: {}\n⏰ Time: {}\n\nCustomer has been notified.",
        "technician_pending_list": "🔧 *Technician Visits Pending*\n\nTotal: {} visits to schedule\n\n",
        "no_technician_pending": "✅ No pending technician visits.",
        "admin_verify_btn": "✅ Verify Payment",
        "admin_reject_btn": "❌ Reject Payment",
        "view_customer_btn": "👤 View Customer",
        "schedule_visit_btn": "🔧 Schedule Visit",
        "confirm_tech_btn": "✅ Confirm Verification",
        "provide_suggestion_btn": "💡 Provide Suggestion",
        "payment_reference_prompt": "📝 *Enter Payment Reference*\n\nPlease enter the customer's payment reference number:\n\n📱 *Tele Birr:* Transaction ID\n🏦 *Bank Transfer:* Reference Number",
        "payment_reference_received": "✅ *Payment Reference Received!*\n\n🎫 Ticket: `{}`\n📝 Reference: `{}`\n💳 Method: {}\n💰 Amount: {} ETB\n\n⏳ Admin will verify the payment manually.",
        "suggestion_provided": "💡 *Suggestion Provided!*\n\n🎫 Ticket: `{}`\n\n📋 *Suggestion:*\n{}\n\n✅ No payment required.\n\nPlease follow the suggestion provided.\n\n⭐ *After following the suggestion, please rate your experience!*",
        "admin_suggestion_instruction": "💡 *Provide Suggestion for Ticket:* `{}`\n\n👤 Customer: {}\n📱 Phone: {}\n🛠️ Issue: {}\n\nPlease provide your suggestion/recommendation for this customer:\n\nExample:\n`The TV needs a software update. Please try resetting the system.`\n\nType your suggestion below:",
        "rating_thanks": "🙏 *Thank You for Your Feedback!*\n\nYour rating helps us improve our service quality.\n\nWe truly value your opinion! ⭐\n\n🔙 You can return to the main menu anytime.",
        "view_ratings_list": "⭐ *All Ratings*\n\nTotal Ratings: {}\nAverage Rating: {:.1f} / 5.0\n\n",
        "no_ratings_yet": "📭 No ratings received yet.",
        "rating_detail": "🎫 Ticket: `{}`\n👤 Customer: {}\n⭐ Rating: {} / 5\n💬 Comment: {}\n📅 Date: {}\n",
    },
    "am": {
        "name": "አማርኛ",
        "flag": "🇪🇹",
        # ... (Amharic translations would go here, truncated for brevity)
        # For the full version, all Amharic translations should be included
    }
}

# Store user language preferences
user_languages = {}

def get_text(user_id, key, *args):
    lang = user_languages.get(user_id, "en")
    text = LANGUAGES.get(lang, LANGUAGES["en"]).get(key, key)
    
    if args and '{}' in text:
        try:
            placeholder_count = text.count('{}')
            if len(args) >= placeholder_count:
                return text.format(*args[:placeholder_count])
            else:
                padded_args = list(args) + [''] * (placeholder_count - len(args))
                return text.format(*padded_args[:placeholder_count])
        except Exception as e:
            logger.error(f"Error formatting text for key '{key}': {e}")
            return text
    return text

# ==================== HELPER FUNCTIONS ====================

def get_category_name(category_id, lang="en"):
    if not category_id:
        return "Unknown Category" if lang == "en" else "ያልታወቀ ምድብ"
    category = PRODUCT_CATEGORIES.get(category_id)
    if not category:
        return "Unknown Category" if lang == "en" else "ያልታወቀ ምድብ"
    return category["name"] if lang == "en" else category["name_am"]

def get_brand_name(category_id, brand_id, lang="en"):
    if not category_id or not brand_id:
        return "Unknown Brand" if lang == "en" else "ያልታወቀ ብራንድ"
    category = PRODUCT_CATEGORIES.get(category_id)
    if category:
        for brand in category["brands"]:
            if brand["id"] == brand_id:
                return brand["name"] if lang == "en" else brand["name_am"]
    return "Unknown Brand" if lang == "en" else "ያልታወቀ ብራንድ"

def get_issue_name(issue_id, lang="en"):
    if not issue_id:
        return "Unknown Issue" if lang == "en" else "ያልታወቀ ችግር"
    for issue in ISSUE_TYPES:
        if issue["id"] == issue_id:
            return issue["name"] if lang == "en" else issue["name_am"]
    return "Unknown Issue" if lang == "en" else "ያልታወቀ ችግር"

def get_service_type_name(service_type, lang="en"):
    if service_type == "suggestion":
        return "💡 Suggestion Only" if lang == "en" else "💡 ምክር ብቻ"
    elif service_type == "technician":
        return "🔧 Technician Required" if lang == "en" else "🔧 ቴክኒሻን ያስፈልጋል"
    return "Unknown" if lang == "en" else "ያልታወቀ"

def get_user_language(user_id):
    return user_languages.get(user_id, "en")

def get_localized_category_name(category_id, user_id):
    lang = get_user_language(user_id)
    return get_category_name(category_id, lang)

def get_localized_brand_name(category_id, brand_id, user_id):
    lang = get_user_language(user_id)
    return get_brand_name(category_id, brand_id, lang)

def get_localized_issue_name(issue_id, user_id):
    lang = get_user_language(user_id)
    return get_issue_name(issue_id, lang)

def get_localized_service_type(service_type, user_id):
    lang = get_user_language(user_id)
    return get_service_type_name(service_type, lang)

def get_rating_display(rating):
    if rating is None:
        return "⭐ Not rated yet"
    return f"⭐ {rating}/5"

def get_guarantee_status(ticket):
    if ticket.get('status') != 'Completed':
        return "🔒 Guarantee not yet active"
    
    expiry = ticket.get('guarantee_expiry')
    if not expiry:
        return "🔒 Guarantee period not set"
    
    try:
        expiry_date = datetime.fromisoformat(expiry)
        if datetime.now() > expiry_date:
            return f"❌ Guarantee expired on {expiry_date.strftime('%Y-%m-%d')}"
        else:
            days_left = (expiry_date - datetime.now()).days
            return f"✅ Guarantee active ({days_left} days remaining)"
    except:
        return "🔒 Guarantee status unavailable"

def generate_payment_reference(ticket_id, user_id, amount):
    secret_key = "YOUR_SECURE_SECRET_KEY_CHANGE_ME"
    data = f"{ticket_id}{user_id}{amount}{datetime.now().timestamp()}"
    return hmac.new(
        secret_key.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()[:16].upper()

# ==================== START AND MENU HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler"""
    user_id = update.effective_user.id
    
    user_sessions[user_id] = {"step": "main_menu"}
    
    if user_id not in user_languages:
        await show_language_selection(update, context)
        return
    
    await show_main_menu(update, context)

async def show_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show language selection"""
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🌐 *Select Your Language / ቋንቋዎን ይምረጡ*\n\nPlease select your preferred language:\nእባክዎ የሚመርጡትን ቋንቋ ይምረጡ:"
    
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set user language"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = query.data.replace("lang_", "")
    
    user_languages[user_id] = lang
    
    lang_name = LANGUAGES[lang]["name"]
    await query.edit_message_text(
        get_text(user_id, "language_changed", lang_name),
        parse_mode='Markdown'
    )
    
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show main menu"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {"step": "main_menu"}
    
    welcome_text = get_text(user_id, "welcome", COMPANY_NAME)
    
    keyboard = [
        [
            InlineKeyboardButton(get_text(user_id, "product_support"), callback_data="product_support"),
            InlineKeyboardButton(get_text(user_id, "faq"), callback_data="faq")
        ],
        [
            InlineKeyboardButton(get_text(user_id, "contact"), callback_data="contact"),
            InlineKeyboardButton(get_text(user_id, "about"), callback_data="about")
        ],
        [
            InlineKeyboardButton(get_text(user_id, "my_tickets"), callback_data="my_tickets")
        ],
        [
            InlineKeyboardButton(get_text(user_id, "payment"), callback_data="make_payment")
        ],
        [
            InlineKeyboardButton("📅 Schedule Appointment", callback_data="schedule_appointment"),
            InlineKeyboardButton("⭐ Rate Service", callback_data="rate_service")
        ],
        [
            InlineKeyboardButton(get_text(user_id, "change_language"), callback_data="change_language")
        ]
    ]
    
    if user_id in ADMIN_USER_IDS:
        keyboard.append([
            InlineKeyboardButton(get_text(user_id, "admin_panel"), callback_data="admin_panel")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.callback_query.edit_message_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# ==================== ADMIN PANEL ====================

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await query.edit_message_text(get_text(user_id, "unauthorized"))
        return
    
    keyboard = [
        ["📋 My Tickets", "📊 All Tickets"],
        ["📊 Export All", "📊 Export Today"],
        ["📋 Pending Review", "💰 Pending Payments"],
        ["🔍 Pending Verification", "🔧 Technician Visits"],
        ["💡 Provide Suggestion", "⭐ View Ratings"],
        ["📊 Dashboard", "🔙 Back to Menu"]
    ]
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    stats = ticket_manager.get_statistics()
    daily_tickets = ticket_manager.get_daily_tickets()
    today_str = datetime.now().strftime("%Y-%m-%d")
    avg_rating = ticket_manager.get_average_rating()
    
    panel_text = get_text(user_id, "admin_panel_text",
        stats['total'],
        today_str,
        len(daily_tickets),
        stats['pending_review'],
        stats['technician_pending'],
        stats['technician_scheduled'],
        stats['pending_payment'],
        stats['pending_verification'],
        stats['suggestion_provided'],
        stats['completed'],
        stats['rated'],
        stats['awaiting_rating'],
        avg_rating
    )
    
    await query.edit_message_text(
        panel_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ==================== RATING SYSTEM ====================

async def handle_rate_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rate service button"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Get completed tickets that haven't been rated yet
    user_tickets = ticket_manager.get_user_tickets(user_id)
    completed_tickets = [t for t in user_tickets if t.get("status") == "Completed" and t.get("rating") is None]
    
    if not completed_tickets:
        # Check if there are any completed tickets that were already rated
        rated_tickets = [t for t in user_tickets if t.get("status") == "Completed" and t.get("rating") is not None]
        
        if rated_tickets:
            message = "⭐ *You have already rated all your completed services!*\n\n"
            message += "Thank you for your feedback! 🙏\n\n"
            message += "Here are your ratings:\n\n"
            
            for ticket in rated_tickets[-5:]:
                message += f"• 🎫 {ticket['ticket_id']} - {get_rating_display(ticket.get('rating'))}\n"
                if ticket.get('rating_comment'):
                    message += f"  💬 {ticket['rating_comment'][:50]}...\n"
        else:
            message = "📭 You have no completed services to rate.\n\n"
            message += "Once your service is completed, you'll be able to rate your experience here!"
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # If only one ticket, show rating directly
    if len(completed_tickets) == 1:
        ticket = completed_tickets[0]
        user_sessions[user_id] = {
            "step": "rating_service",
            "rating_ticket_id": ticket['ticket_id']
        }
        await show_rating_options(update, context, ticket)
        return
    
    # Show list of completed tickets to rate
    message = "⭐ *Rate Your Service*\n\n"
    message += "Please select the service you want to rate:\n\n"
    
    keyboard = []
    for ticket in completed_tickets:
        message += f"• 🎫 {ticket['ticket_id']} - {ticket['category_name']}\n"
        message += f"  📅 Completed: {ticket.get('completed_at', '').split('T')[0] if ticket.get('completed_at') else 'Unknown'}\n\n"
        keyboard.append([
            InlineKeyboardButton(
                f"⭐ Rate {ticket['ticket_id']}",
                callback_data=f"rate_ticket_{ticket['ticket_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")])
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_rating_options(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket: Dict) -> None:
    """Show rating options for a ticket"""
    user_id = update.effective_user.id
    query = update.callback_query if hasattr(update, 'callback_query') else None
    
    rating_text = f"⭐ *Rate Your Service*\n\n"
    rating_text += f"🎫 *Ticket:* `{ticket['ticket_id']}`\n"
    rating_text += f"📱 *Service:* {ticket['category_name']}\n"
    rating_text += f"🛠️ *Issue:* {ticket['issue_name']}\n"
    rating_text += f"📅 *Completed:* {ticket.get('completed_at', '').split('T')[0] if ticket.get('completed_at') else 'Unknown'}\n\n"
    rating_text += get_text(user_id, "rating_options")
    
    keyboard = [
        [
            InlineKeyboardButton("⭐ 1", callback_data=f"rating_1_{ticket['ticket_id']}"),
            InlineKeyboardButton("⭐⭐ 2", callback_data=f"rating_2_{ticket['ticket_id']}"),
            InlineKeyboardButton("⭐⭐⭐ 3", callback_data=f"rating_3_{ticket['ticket_id']}"),
            InlineKeyboardButton("⭐⭐⭐⭐ 4", callback_data=f"rating_4_{ticket['ticket_id']}"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐ 5", callback_data=f"rating_5_{ticket['ticket_id']}")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_rating_list")]
    ]
    
    if query:
        await query.edit_message_text(
            rating_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            rating_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def submit_rating_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rating submission"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Parse rating data: rating_5_TICKET123
    parts = data.split("_")
    rating = int(parts[1])
    ticket_id = parts[2]
    
    # Store the rating temporarily and ask for optional comment
    user_sessions[user_id] = {
        "step": "rating_comment",
        "rating_ticket_id": ticket_id,
        "rating_value": rating
    }
    
    keyboard = [
        [InlineKeyboardButton("⏭️ Skip Comment", callback_data=f"rating_skip_{ticket_id}")]
    ]
    
    await query.edit_message_text(
        get_text(user_id, "rating_comment_prompt"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def submit_rating_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rating comment submission"""
    query = update.callback_query
    user_id = query.from_user.id
    session = user_sessions.get(user_id, {})
    
    ticket_id = session.get("rating_ticket_id")
    rating = session.get("rating_value")
    
    if not ticket_id or not rating:
        await query.edit_message_text("❌ Error processing rating. Please try again.")
        return
    
    if query.data.startswith("rating_skip_"):
        comment = ""
    else:
        # This would be a text message handler
        return
    
    await save_rating_and_notify(update, context, ticket_id, rating, comment)

async def process_rating_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process rating comment from text message"""
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get("step") != "rating_comment":
        return
    
    ticket_id = session.get("rating_ticket_id")
    rating = session.get("rating_value")
    comment = update.message.text.strip()
    
    if not ticket_id or not rating:
        await update.message.reply_text("❌ Error processing rating. Please try again.")
        return
    
    await save_rating_and_notify_message(update, context, ticket_id, rating, comment)

async def save_rating_and_notify(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str, rating: int, comment: str) -> None:
    """Save rating and notify parties"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if ticket_manager.add_rating(ticket_id, rating, comment):
        ticket = ticket_manager.get_ticket(ticket_id)
        
        # Thank the customer
        await query.edit_message_text(
            get_text(user_id, "rating_received", rating, comment if comment else "No comment provided"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")]
            ]),
            parse_mode='Markdown'
        )
        
        # Notify admins
        for admin_id in ADMIN_USER_IDS:
            try:
                admin_message = f"⭐ *New Rating Received*\n\n"
                admin_message += f"🎫 Ticket: `{ticket_id}`\n"
                admin_message += f"👤 Customer: {ticket.get('user_name', 'Unknown')}\n"
                admin_message += f"📱 Phone: {ticket.get('phone', 'Not provided')}\n"
                admin_message += f"⭐ Rating: {rating}/5\n"
                if comment:
                    admin_message += f"💬 Comment: {comment}\n"
                admin_message += f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin about rating: {e}")
        
        user_sessions[user_id] = {"step": "main_menu"}
    else:
        await query.edit_message_text(
            "❌ Failed to submit rating. Please try again.",
            parse_mode='Markdown'
        )

async def save_rating_and_notify_message(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str, rating: int, comment: str) -> None:
    """Save rating and notify parties from message"""
    user_id = update.effective_user.id
    
    if ticket_manager.add_rating(ticket_id, rating, comment):
        ticket = ticket_manager.get_ticket(ticket_id)
        
        # Thank the customer
        await update.message.reply_text(
            get_text(user_id, "rating_received", rating, comment if comment else "No comment provided"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")]
            ]),
            parse_mode='Markdown'
        )
        
        # Notify admins
        for admin_id in ADMIN_USER_IDS:
            try:
                admin_message = f"⭐ *New Rating Received*\n\n"
                admin_message += f"🎫 Ticket: `{ticket_id}`\n"
                admin_message += f"👤 Customer: {ticket.get('user_name', 'Unknown')}\n"
                admin_message += f"📱 Phone: {ticket.get('phone', 'Not provided')}\n"
                admin_message += f"⭐ Rating: {rating}/5\n"
                if comment:
                    admin_message += f"💬 Comment: {comment}\n"
                admin_message += f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin about rating: {e}")
        
        user_sessions[user_id] = {"step": "main_menu"}
    else:
        await update.message.reply_text(
            "❌ Failed to submit rating. Please try again.",
            parse_mode='Markdown'
        )

async def view_ratings_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View all ratings for admin"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text(user_id, "unauthorized"))
        return
    
    all_tickets = ticket_manager.get_all_tickets()
    rated_tickets = [t for t in all_tickets if t.get("rating") is not None]
    
    if not rated_tickets:
        await update.message.reply_text(
            get_text(user_id, "no_ratings_yet"),
            parse_mode='Markdown'
        )
        return
    
    avg_rating = ticket_manager.get_average_rating()
    message = get_text(user_id, "view_ratings_list", len(rated_tickets), avg_rating)
    
    # Show latest ratings first
    for ticket in sorted(rated_tickets, key=lambda x: x.get("rating_date", ""), reverse=True)[:15]:
        message += get_text(user_id, "rating_detail",
            ticket['ticket_id'],
            ticket.get('user_name', 'Unknown'),
            ticket.get('rating', 'N/A'),
            ticket.get('rating_comment', 'No comment'),
            ticket.get('rating_date', '').split('T')[0] if ticket.get('rating_date') else 'Unknown'
        )
        message += "\n"
    
    if len(rated_tickets) > 15:
        message += f"\n... and {len(rated_tickets) - 15} more ratings."
    
    keyboard = [[InlineKeyboardButton("📊 Export Ratings", callback_data="admin_export_ratings")]]
    
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def export_ratings_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export ratings to CSV"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await query.edit_message_text(get_text(user_id, "unauthorized"))
        return
    
    await query.edit_message_text("⏳ Generating ratings export...")
    
    all_tickets = ticket_manager.get_all_tickets()
    rated_tickets = [t for t in all_tickets if t.get("rating") is not None]
    
    if not rated_tickets:
        await query.edit_message_text("📭 No ratings to export.")
        return
    
    csv_content = """Ticket ID,Customer Name,Phone,Category,Issue,Rating,Comment,Rated Date\n"""
    
    for ticket in rated_tickets:
        row = [
            ticket.get('ticket_id', ''),
            ticket.get('user_name', ''),
            ticket.get('phone', ''),
            ticket.get('category_name', ''),
            ticket.get('issue_name', ''),
            ticket.get('rating', ''),
            f'"{ticket.get("rating_comment", "").replace("\\n", " ")}"',
            ticket.get('rating_date', '').split('T')[0] if ticket.get('rating_date') else ''
        ]
        csv_content += ",".join(str(field) for field in row) + "\n"
    
    filename = f"ratings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(filename, 'w', encoding='utf-8-sig') as f:
        f.write(csv_content)
    
    with open(filename, 'rb') as f:
        await query.message.reply_document(
            document=f,
            filename=filename,
            caption=f"⭐ Ratings Export\n📋 {len(rated_tickets)} ratings exported\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
    
    os.remove(filename)
    await query.answer("Export complete!")

# ==================== CALLBACK BUTTON HANDLER ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Language selection
    if data.startswith("lang_"):
        await set_language(update, context)
        return
    
    elif data == "change_language":
        await show_language_selection(update, context)
        return
    
    elif data == "back_to_main":
        await show_main_menu(update, context)
        return
    
    elif data == "faq":
        keyboard = [[InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main")]]
        await query.edit_message_text(
            get_text(user_id, "faq_text"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    elif data == "contact":
        keyboard = [[InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main")]]
        await query.edit_message_text(
            get_text(user_id, "contact_text", COMPANY_PHONE, COMPANY_EMAIL, WORKING_HOURS),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    elif data == "about":
        keyboard = [[InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main")]]
        await query.edit_message_text(
            get_text(user_id, "about_text", COMPANY_NAME),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    elif data == "admin_panel":
        await show_admin_panel(update, context)
        return
    
    elif data == "product_support":
        await show_categories(query)
        return
    
    elif data == "my_tickets":
        await show_my_tickets(query)
        return
    
    elif data == "make_payment":
        await handle_make_payment(update, context)
        return
    
    elif data == "schedule_appointment":
        await query.edit_message_text(
            "📅 *Schedule Appointment*\n\nPlease use the 'My Tickets' button to view your tickets and schedule appointments.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 My Tickets", callback_data="my_tickets")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # ==================== RATING HANDLERS ====================
    
    elif data == "rate_service":
        await handle_rate_service(update, context)
        return
    
    elif data.startswith("rate_ticket_"):
        ticket_id = data.replace("rate_ticket_", "")
        ticket = ticket_manager.get_ticket(ticket_id)
        if ticket:
            user_sessions[user_id] = {
                "step": "rating_service",
                "rating_ticket_id": ticket_id
            }
            await show_rating_options(update, context, ticket)
        return
    
    elif data.startswith("rating_"):
        # rating_5_TICKET123
        parts = data.split("_")
        rating = int(parts[1])
        ticket_id = parts[2]
        
        # Store rating and ask for optional comment
        user_sessions[user_id] = {
            "step": "rating_comment",
            "rating_ticket_id": ticket_id,
            "rating_value": rating
        }
        
        keyboard = [
            [InlineKeyboardButton("⏭️ Skip Comment", callback_data=f"rating_skip_{ticket_id}")]
        ]
        
        await query.edit_message_text(
            get_text(user_id, "rating_comment_prompt"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    elif data.startswith("rating_skip_"):
        ticket_id = data.replace("rating_skip_", "")
        rating = user_sessions.get(user_id, {}).get("rating_value")
        
        if not rating:
            await query.edit_message_text("❌ Error processing rating. Please try again.")
            return
        
        await save_rating_and_notify(update, context, ticket_id, rating, "")
        return
    
    elif data == "back_to_rating_list":
        await handle_rate_service(update, context)
        return
    
    # ==================== ADMIN RATINGS ====================
    
    elif data == "admin_export_ratings":
        await export_ratings_csv(update, context)
        return
    
    # ==================== SERVICE TYPE SELECTION ====================
    
    elif data == "service_type_suggestion":
        user_sessions[user_id]["service_type"] = "suggestion"
        user_sessions[user_id]["step"] = "describing_issue"
        await show_description_prompt(update, context)
        return
    
    elif data == "service_type_technician":
        user_sessions[user_id]["service_type"] = "technician"
        user_sessions[user_id]["step"] = "describing_issue"
        await show_description_prompt(update, context)
        return
    
    # ==================== ADMIN FUNCTIONS ====================
    
    elif data.startswith("schedule_visit_"):
        ticket_id = data.replace("schedule_visit_", "")
        await schedule_technician_visit(update, context, ticket_id)
        return
    
    elif data.startswith("view_customer_"):
        ticket_id = data.replace("view_customer_", "")
        await view_customer_details(update, context, ticket_id)
        return
    
    elif data.startswith("confirm_tech_"):
        ticket_id = data.replace("confirm_tech_", "")
        await confirm_technician_verification(update, context, ticket_id)
        return
    
    elif data.startswith("provide_suggestion_"):
        ticket_id = data.replace("provide_suggestion_", "")
        await provide_suggestion(update, context, ticket_id)
        return
    
    elif data.startswith("admin_verify_payment_"):
        ticket_id = data.replace("admin_verify_payment_", "")
        await admin_verify_payment(update, context, ticket_id)
        return
    
    elif data.startswith("admin_reject_payment_"):
        ticket_id = data.replace("admin_reject_payment_", "")
        await admin_reject_payment(update, context, ticket_id)
        return
    
    # ==================== CATEGORY/Brand/Issue ====================
    
    elif data.startswith("category_"):
        category_id = data.replace("category_", "")
        user_sessions[user_id] = {
            "step": "selecting_brand",
            "category": category_id,
            "category_name": get_localized_category_name(category_id, user_id)
        }
        await show_brands(query, category_id)
        return
    
    elif data.startswith("brand_"):
        brand_id = data.replace("brand_", "")
        category_id = user_sessions.get(user_id, {}).get("category")
        user_sessions[user_id]["brand"] = brand_id
        user_sessions[user_id]["brand_name"] = get_localized_brand_name(category_id, brand_id, user_id)
        user_sessions[user_id]["step"] = "selecting_service_type"
        await show_service_type_selection(query)
        return
    
    elif data.startswith("issue_"):
        issue_id = data.replace("issue_", "")
        user_sessions[user_id]["issue"] = issue_id
        user_sessions[user_id]["issue_name"] = get_localized_issue_name(issue_id, user_id)
        user_sessions[user_id]["step"] = "selecting_service_type"
        await show_service_type_selection(query)
        return
    
    # ==================== TICKET STATUS ====================
    
    elif data.startswith("check_ticket_"):
        ticket_id = data.replace("check_ticket_", "")
        await show_ticket_status(update, context, ticket_id)
        return
    
    # ==================== BACK BUTTONS ====================
    
    elif data == "back_to_categories":
        await show_categories(query)
        return
    
    elif data == "back_to_issues":
        await show_issue_types(query)
        return
    
    else:
        await query.edit_message_text(
            "🤔 I'm not sure what you need. Please use the menu buttons below.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")]
            ])
        )

# ==================== SHOW FUNCTIONS ====================

async def show_categories(query):
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    user_sessions[user_id]["step"] = "selecting_category"
    
    keyboard = []
    for cat_id, cat_data in PRODUCT_CATEGORIES.items():
        category_name = cat_data["name"] if lang == "en" else cat_data["name_am"]
        keyboard.append([InlineKeyboardButton(
            category_name, 
            callback_data=f"category_{cat_id}"
        )])
    
    keyboard.append([InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main")])
    
    await query.edit_message_text(
        get_text(user_id, "select_category"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_brands(query, category_id):
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    
    category = PRODUCT_CATEGORIES.get(category_id)
    
    if not category:
        await show_categories(query)
        return
    
    keyboard = []
    for brand in category["brands"]:
        brand_name = brand["name"] if lang == "en" else brand["name_am"]
        keyboard.append([InlineKeyboardButton(
            brand_name, 
            callback_data=f"brand_{brand['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(get_text(user_id, "back"), callback_data="back_to_categories")])
    
    category_name = category["name"] if lang == "en" else category["name_am"]
    
    await query.edit_message_text(
        get_text(user_id, "select_brand", category_name),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_issue_types(query):
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    
    keyboard = []
    for issue in ISSUE_TYPES:
        issue_name = issue["name"] if lang == "en" else issue["name_am"]
        keyboard.append([InlineKeyboardButton(
            issue_name, 
            callback_data=f"issue_{issue['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(get_text(user_id, "back"), callback_data="back_to_categories")])
    
    await query.edit_message_text(
        get_text(user_id, "select_issue"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_service_type_selection(query):
    """Show service type selection (Suggestion Only vs Technician Required)"""
    user_id = query.from_user.id
    
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, "service_type_suggestion"), callback_data="service_type_suggestion")],
        [InlineKeyboardButton(get_text(user_id, "service_type_technician"), callback_data="service_type_technician")],
        [InlineKeyboardButton(get_text(user_id, "back"), callback_data="back_to_issues")]
    ]
    
    await query.edit_message_text(
        get_text(user_id, "select_service_type"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_description_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show description prompt"""
    query = update.callback_query
    user_id = query.from_user.id
    session = user_sessions.get(user_id, {})
    
    service_type_display = get_localized_service_type(session.get("service_type", "technician"), user_id)
    
    keyboard = [[InlineKeyboardButton(get_text(user_id, "back"), callback_data="back_to_service_type")]]
    
    await query.edit_message_text(
        get_text(user_id, "describe_issue", 
            session.get('category_name', 'Unknown'),
            session.get('brand_name', 'Unknown'),
            session.get('issue_name', 'Unknown'),
            service_type_display),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_my_tickets(query):
    user_id = query.from_user.id
    user_tickets = ticket_manager.get_user_tickets(user_id)
    
    if not user_tickets:
        await query.edit_message_text(get_text(user_id, "no_tickets"))
        return
    
    message = get_text(user_id, "your_tickets")
    for ticket in user_tickets[-5:]:
        status_emoji = {
            "Pending Review": get_text(user_id, "status_pending_review"),
            "Technician Scheduled": get_text(user_id, "status_technician_scheduled"),
            "Awaiting Payment": get_text(user_id, "status_awaiting_payment"),
            "Awaiting Verification": get_text(user_id, "status_awaiting_verification"),
            "Payment Confirmed": get_text(user_id, "status_payment_confirmed"),
            "In Progress": get_text(user_id, "status_in_progress"),
            "Completed": get_text(user_id, "status_completed"),
            "Suggestion Provided": get_text(user_id, "status_suggestion_provided")
        }.get(ticket['status'], get_text(user_id, "status_default"))
        
        rating_display = get_rating_display(ticket.get('rating'))
        
        message += f"{status_emoji} *{ticket['ticket_id']}*\n"
        message += f"📱 {ticket['category_name']}\n"
        message += f"Status: {ticket['status']}\n"
        service_type = ticket.get('service_type', 'technician')
        service_display = "💡 Suggestion" if service_type == "suggestion" else "🔧 Technician"
        message += f"Service: {service_display}\n"
        message += f"⭐ {rating_display}\n"
        if ticket.get('payment_amount', 0) > 0:
            message += f"💰 {ticket.get('payment_amount', 0)} ETB\n"
        message += f"📅 {ticket['created_at'].split('T')[0]}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("📋 Check Ticket Status", callback_data=f"check_ticket_{ticket['ticket_id']}")],
        [InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== PAYMENT HANDLERS ====================

async def handle_make_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle make payment button"""
    query = update.callback_query
    user_id = query.from_user.id
    
    user_tickets = ticket_manager.get_user_tickets(user_id)
    pending_tickets = [t for t in user_tickets if t.get("payment_status") in ["Pending", "Pending Verification"] and t.get("payment_amount", 0) > 0]
    
    if not pending_tickets:
        await query.edit_message_text(
            "📭 You have no pending payments.\n\n"
            "If you have a ticket, please wait for the technician to provide a response.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")]
            ])
        )
        return
    
    if len(pending_tickets) == 1:
        ticket = pending_tickets[0]
        await show_payment_options(update, context, ticket)
        return
    
    message = "💰 *Your Pending Payments*\n\n"
    keyboard = []
    
    for ticket in pending_tickets:
        amount = ticket.get("payment_amount", 0)
        status = "⏳ Pending" if ticket.get("payment_status") == "Pending" else "🔍 Verification"
        message += f"• 🎫 {ticket['ticket_id']} - {amount} ETB ({status})\n"
        keyboard.append([
            InlineKeyboardButton(
                f"Pay {ticket['ticket_id']} - {amount} ETB",
                callback_data=f"pay_ticket_{ticket['ticket_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")])
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_payment_options(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket: Dict) -> None:
    """Show payment options for a ticket"""
    user_id = update.effective_user.id
    query = update.callback_query
    
    amount = ticket.get("payment_amount", 0)
    ticket_id = ticket['ticket_id']
    
    payment_text = get_text(user_id, "payment_options", amount)
    
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, "payment_telebirr"), callback_data=f"pay_telebirr_{ticket_id}")],
        [InlineKeyboardButton(get_text(user_id, "payment_bank"), callback_data=f"pay_bank_{ticket_id}")],
        [InlineKeyboardButton("📸 Upload Screenshot", callback_data=f"screenshot_pay_{ticket_id}")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(
        payment_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== TICKET CREATION ====================

async def create_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new ticket"""
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})
    
    user = update.effective_user
    username = user.username or "No username"
    first_name = user.first_name or "Unknown"
    
    service_type = session.get("service_type", "technician")
    
    ticket_data = {
        "user_id": user_id,
        "user_name": session.get("user_name", first_name),
        "username": username,
        "phone": session.get("phone", ""),
        "location": session.get("location", "Not shared"),
        "location_lat": session.get("location_lat", ""),
        "location_lon": session.get("location_lon", ""),
        "location_link": session.get("location_link", ""),
        "category": session.get("category", ""),
        "category_name": session.get("category_name", ""),
        "brand": session.get("brand", ""),
        "brand_name": session.get("brand_name", ""),
        "issue_type": session.get("issue", ""),
        "issue_name": session.get("issue_name", ""),
        "service_type": service_type,
        "description": session.get("description", ""),
        "language": get_user_language(user_id)
    }
    
    ticket = ticket_manager.create_ticket(user_id, ticket_data)
    ticket_id = ticket["ticket_id"]
    
    user_sessions[user_id] = {"step": "main_menu"}
    
    await update.message.reply_text(
        get_text(user_id, "processing"),
        reply_markup=ReplyKeyboardRemove()
    )
    
    location_display = session.get("location", "Not shared")
    if location_display and location_display != "Not shared" and location_display.startswith("http"):
        location_display = f"[{get_text(user_id, 'view_on_map')}]({location_display})"
    
    service_type_display = get_localized_service_type(service_type, user_id)
    
    if service_type == "suggestion":
        next_step = "Our team will review your request and provide a suggestion within 24 hours. No technician visit required."
    else:
        next_step = "Our technician will review your request and schedule a visit to verify the issue in person."
    
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, "check_ticket"), callback_data=f"check_ticket_{ticket_id}")],
        [InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main")]
    ]
    
    await update.message.reply_text(
        get_text(user_id, "ticket_created",
            ticket_id,
            session.get('user_name', 'Unknown'),
            session.get('phone', get_text(user_id, 'location_not_provided')),
            location_display,
            session.get('category_name', 'Unknown'),
            session.get('brand_name', 'Unknown'),
            session.get('issue_name', 'Unknown'),
            service_type_display,
            next_step
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )
    
    # Notify admins
    for admin_id in ADMIN_USER_IDS:
        try:
            description = session.get('description', 'No description provided')
            if len(description) > 200:
                description = description[:200] + "..."
            
            admin_message = f"""📋 *New Ticket Created!*

🎫 *Ticket:* `{ticket_id}`
👤 *Customer:* {session.get('user_name', 'Unknown')}
📱 *Phone:* {session.get('phone', 'Not provided')}
📱 *Product:* {session.get('category_name', 'Unknown')}
🔧 *Service:* {session.get('issue_name', 'Unknown')}
🏷️ *Brand:* {session.get('brand_name', 'Unknown')}
💡 *Service Type:* {service_type_display}

📝 *Description:*
{description}

📍 *Location:* {location_display if location_display != 'Not shared' else 'Not shared'}

📅 *Created:* {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
            
            if service_type == "suggestion":
                admin_message += f"\n\n💡 *Action:* Provide a suggestion to the customer."
                buttons = [
                    [InlineKeyboardButton("💡 Provide Suggestion", callback_data=f"provide_suggestion_{ticket_id}")],
                    [InlineKeyboardButton("👤 View Customer", callback_data=f"view_customer_{ticket_id}")]
                ]
            else:
                admin_message += f"\n\n🔧 *Action:* Schedule a technician visit."
                buttons = [
                    [InlineKeyboardButton("🔧 Schedule Visit", callback_data=f"schedule_visit_{ticket_id}")],
                    [InlineKeyboardButton("👤 View Customer", callback_data=f"view_customer_{ticket_id}")]
                ]
            
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
    
    logger.info(f"✅ Ticket created: {ticket_id} for {session.get('user_name', 'Unknown')}")

# ==================== ADMIN FUNCTIONS ====================

async def schedule_technician_visit(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str) -> None:
    """Schedule a technician visit"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await query.edit_message_text(get_text(user_id, "unauthorized"))
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await query.edit_message_text("❌ Ticket not found.")
        return
    
    user_sessions[user_id] = {
        "step": "scheduling_technician",
        "schedule_ticket_id": ticket_id
    }
    
    location = ticket.get('location', 'Not shared')
    if location and location.startswith('http'):
        location = "📍 Shared via Google Maps"
    
    service_type = ticket.get('service_type', 'technician')
    service_display = "💡 Suggestion" if service_type == "suggestion" else "🔧 Technician"
    
    instruction = get_text(user_id, "admin_schedule_visit",
        ticket_id,
        ticket.get('user_name', 'Unknown'),
        ticket.get('phone', 'Not provided'),
        location,
        service_display
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main")]]
    
    await query.edit_message_text(
        instruction,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def view_customer_details(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str) -> None:
    """View customer details"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await query.edit_message_text(get_text(user_id, "unauthorized"))
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await query.edit_message_text("❌ Ticket not found.")
        return
    
    service_type = ticket.get('service_type', 'technician')
    service_display = "💡 Suggestion Only" if service_type == "suggestion" else "🔧 Technician Required"
    rating_display = get_rating_display(ticket.get('rating'))
    
    customer_message = f"""👤 *Customer Details*

🎫 *Ticket:* `{ticket_id}`

📋 *Personal Information:*
• *Name:* {ticket.get('user_name', 'Unknown')}
• *Username:* @{ticket.get('username', 'N/A')}
• *Phone:* {ticket.get('phone', 'Not provided')}

📍 *Location:*
{ticket.get('location', 'Not shared')}

📱 *Product Details:*
• *Category:* {ticket.get('category_name', 'Unknown')}
• *Brand:* {ticket.get('brand_name', 'Unknown')}
• *Issue:* {ticket.get('issue_name', 'Unknown')}
• *Service Type:* {service_display}

📝 *Description:*
{ticket.get('description', 'No description provided')}

📅 *Created:* {ticket.get('created_at', '').split('T')[0] if ticket.get('created_at') else 'Unknown'}
🔄 *Status:* {ticket.get('status', 'Pending')}
💰 *Payment Status:* {ticket.get('payment_status', 'Not Required')}
⭐ *Rating:* {rating_display}"""
    
    if service_type == "suggestion":
        buttons = [
            [InlineKeyboardButton("💡 Provide Suggestion", callback_data=f"provide_suggestion_{ticket_id}")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("🔧 Schedule Visit", callback_data=f"schedule_visit_{ticket_id}")],
            [InlineKeyboardButton("✅ Confirm Verification", callback_data=f"confirm_tech_{ticket_id}")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
    
    await query.edit_message_text(
        customer_message,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )

async def confirm_technician_verification(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str) -> None:
    """Confirm technician verification"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await query.edit_message_text(get_text(user_id, "unauthorized"))
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await query.edit_message_text("❌ Ticket not found.")
        return
    
    user_sessions[user_id] = {
        "step": "technician_verification",
        "verify_ticket_id": ticket_id
    }
    
    instruction = f"""🔧 *Technician Verification & Quote*

For Ticket: `{ticket_id}`
👤 Customer: {ticket.get('user_name', 'Unknown')}
📱 Phone: {ticket.get('phone', 'Not provided')}

Please provide the verification details:

📝 *Findings:* What did the technician find?

📋 *Verified Issue:* What is the confirmed issue?

📦 *Materials Needed:* (optional)
💰 *Material Cost:* (optional, in ETB)

💵 *Service Fee:* (optional, in ETB)

⚠️ *IMPORTANT:* If the issue is not valid or no repair is needed, set all costs to 0.

Format:
`Findings | Verified Issue | Materials | Material Cost | Service Fee`

Example:
`Power supply faulty | Need power supply board replacement | Power supply board | 850 | 350`"""
    
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main")]]
    
    await query.edit_message_text(
        instruction,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def provide_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str) -> None:
    """Provide a suggestion for a ticket"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await query.edit_message_text(get_text(user_id, "unauthorized"))
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await query.edit_message_text("❌ Ticket not found.")
        return
    
    user_sessions[user_id] = {
        "step": "providing_suggestion",
        "suggestion_ticket_id": ticket_id
    }
    
    instruction = get_text(user_id, "admin_suggestion_instruction",
        ticket_id,
        ticket.get('user_name', 'Unknown'),
        ticket.get('phone', 'Not provided'),
        ticket.get('issue_name', 'Unknown')
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main")]]
    
    await query.edit_message_text(
        instruction,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str) -> None:
    """Admin verifies payment"""
    query = update.callback_query
    admin_id = query.from_user.id
    
    if admin_id not in ADMIN_USER_IDS:
        await query.edit_message_text(get_text(admin_id, "unauthorized"))
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await query.edit_message_text("❌ Ticket not found.")
        return
    
    amount = ticket.get("payment_amount", 0)
    method = ticket.get("payment_method", "Unknown")
    reference = ticket.get("payment_reference", "Not provided")
    
    if ticket_manager.verify_payment(ticket_id, True, json.dumps({
        "verified_by_admin": admin_id,
        "verified_at": datetime.now().isoformat()
    })):
        ticket_manager.update_status(ticket_id, "Payment Confirmed")
        
        method_display = "Tele Birr" if method == "telebirr" else "Bank Transfer"
        if method == "screenshot":
            method_display = "📸 Screenshot"
        
        await query.edit_message_text(
            f"✅ *Payment Verified by Admin*\n\n"
            f"🎫 Ticket: `{ticket_id}`\n"
            f"👤 Customer: {ticket.get('user_name', 'Unknown')}\n"
            f"💰 Amount: {amount} ETB\n"
            f"💳 Method: {method_display}\n"
            f"📝 Reference: `{reference}`\n\n"
            f"✅ Payment has been confirmed.",
            parse_mode='Markdown'
        )
        
        # Notify customer
        try:
            customer_message = f"""✅ *Payment Confirmed!*

🎫 Ticket: `{ticket_id}`
💰 Amount: {amount} ETB

Your payment has been confirmed. We will proceed with the service.

🔒 *1-Year Guarantee:* All repairs are covered for 1 year!

⭐ *After service completion, you will be asked to rate your experience!*"""
            
            await context.bot.send_message(
                chat_id=ticket['user_id'],
                text=customer_message,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Check Ticket Status", callback_data=f"check_ticket_{ticket_id}")]
                ]),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify customer: {e}")
    else:
        await query.edit_message_text("❌ Failed to verify payment. Please try again.")

async def admin_reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str) -> None:
    """Admin rejects payment"""
    query = update.callback_query
    admin_id = query.from_user.id
    
    if admin_id not in ADMIN_USER_IDS:
        await query.edit_message_text(get_text(admin_id, "unauthorized"))
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await query.edit_message_text("❌ Ticket not found.")
        return
    
    amount = ticket.get("payment_amount", 0)
    
    if ticket_manager.verify_payment(ticket_id, False, json.dumps({
        "rejected_by_admin": admin_id,
        "rejected_at": datetime.now().isoformat()
    })):
        ticket_manager.update_status(ticket_id, "Payment Failed")
        
        await query.edit_message_text(
            f"❌ *Payment Rejected by Admin*\n\n"
            f"🎫 Ticket: `{ticket_id}`\n"
            f"👤 Customer: {ticket.get('user_name', 'Unknown')}\n"
            f"💰 Amount: {amount} ETB\n\n"
            f"Payment has been rejected.",
            parse_mode='Markdown'
        )
        
        # Notify customer
        try:
            await context.bot.send_message(
                chat_id=ticket['user_id'],
                text=f"❌ *Payment Verification Failed*\n\n"
                     f"🎫 Ticket: `{ticket_id}`\n"
                     f"💰 Amount: {amount} ETB\n\n"
                     f"We could not verify your payment. Please check:\n"
                     f"• The reference number is correct\n"
                     f"• The amount matches\n"
                     f"• The payment was completed\n\n"
                     f"If you need assistance, please contact support.\n\n"
                     f"📱 {COMPANY_PHONE}\n"
                     f"📧 {COMPANY_EMAIL}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Try Again", callback_data="make_payment")],
                    [InlineKeyboardButton("📞 Contact Support", callback_data="contact")]
                ]),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify customer: {e}")
    else:
        await query.edit_message_text("❌ Failed to reject payment. Please try again.")

# ==================== MESSAGE HANDLER ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages"""
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})
    step = session.get("step", "")
    
    # Schedule Technician (Admin)
    if step == "scheduling_technician" and user_id in ADMIN_USER_IDS:
        await process_technician_schedule(update, context)
        return
    
    # Technician Verification (Admin)
    elif step == "technician_verification" and user_id in ADMIN_USER_IDS:
        await process_technician_verification(update, context)
        return
    
    # Provide Suggestion (Admin)
    elif step == "providing_suggestion" and user_id in ADMIN_USER_IDS:
        await process_suggestion_provision(update, context)
        return
    
    # Rating Comment
    elif step == "rating_comment":
        await process_rating_comment(update, context)
        return
    
    # Screenshot Upload
    elif step == "screenshot_upload":
        if update.message.photo or update.message.document:
            await process_screenshot_upload(update, context)
            return
        else:
            await update.message.reply_text(
                "📸 *Please upload a screenshot of your payment.*\n\n"
                "Send a photo or document showing your payment confirmation.",
                parse_mode='Markdown'
            )
            return
    
    # Handle description input
    elif step == "describing_issue":
        session["description"] = update.message.text
        session["step"] = "asking_name"
        await update.message.reply_text(
            get_text(user_id, "ask_name"),
            parse_mode='Markdown'
        )
        return
    
    # Handle name input
    elif step == "asking_name":
        if len(update.message.text.strip()) < 2:
            await update.message.reply_text(get_text(user_id, "name_too_short"))
            return
        
        session["user_name"] = update.message.text.strip()
        session["step"] = "asking_phone"
        
        await update.message.reply_text(
            get_text(user_id, "ask_phone", session["user_name"]),
            parse_mode='Markdown'
        )
        return
    
    # Handle phone input
    elif step == "asking_phone":
        phone = update.message.text.strip()
        if len(phone) < 10:
            await update.message.reply_text(get_text(user_id, "phone_invalid"))
            return
        
        session["phone"] = phone
        session["step"] = "asking_location"
        
        keyboard = [
            [KeyboardButton(get_text(user_id, "share_location"), request_location=True)],
            [KeyboardButton(get_text(user_id, "skip_location"))]
        ]
        location_keyboard = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await update.message.reply_text(
            get_text(user_id, "ask_location", phone),
            reply_markup=location_keyboard,
            parse_mode='Markdown'
        )
        return
    
    # Handle location skip
    elif step == "asking_location":
        if update.message.text == get_text(user_id, "skip_location"):
            session["location"] = "Not shared"
            session["location_lat"] = ""
            session["location_lon"] = ""
            session["location_link"] = ""
            session["language"] = get_user_language(user_id)
            await create_ticket(update, context)
            return
        else:
            keyboard = [
                [KeyboardButton(get_text(user_id, "share_location"), request_location=True)],
                [KeyboardButton(get_text(user_id, "skip_location"))]
            ]
            location_keyboard = ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await update.message.reply_text(
                get_text(user_id, "location_reminder"),
                reply_markup=location_keyboard,
                parse_mode='Markdown'
            )
            return
    
    # Handle location
    if update.message.location and step == "asking_location":
        location = update.message.location
        lat = location.latitude
        lon = location.longitude
        
        google_maps_link = f"https://www.google.com/maps?q={lat},{lon}"
        
        session["location"] = google_maps_link
        session["location_lat"] = str(lat)
        session["location_lon"] = str(lon)
        session["location_link"] = google_maps_link
        session["language"] = get_user_language(user_id)
        
        await update.message.reply_text(
            get_text(user_id, "location_received", google_maps_link),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        await create_ticket(update, context)
        return
    
    # Default message
    await update.message.reply_text(
        get_text(user_id, "default_message"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main")]
        ])
    )

# ==================== PROCESS FUNCTIONS ====================

async def process_technician_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process technician schedule input from admin"""
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text(user_id, "unauthorized"))
        return
    
    ticket_id = session.get("schedule_ticket_id")
    if not ticket_id:
        await update.message.reply_text("❌ No ticket selected.")
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await update.message.reply_text("❌ Ticket not found.")
        return
    
    text = update.message.text.strip()
    
    # Parse the input: Name | Phone | Date | Time
    parts = text.split('|')
    if len(parts) < 4:
        await update.message.reply_text(
            "❌ Please use the correct format:\n\n"
            "`Name | Phone | Date (YYYY-MM-DD) | Time`\n\n"
            "Example: `Abebe Kebede | 0912345678 | 2024-01-20 | 10:00 AM`",
            parse_mode='Markdown'
        )
        return
    
    technician_name = parts[0].strip()
    technician_phone = parts[1].strip()
    visit_date = parts[2].strip()
    visit_time = parts[3].strip()
    
    # Validate date format
    try:
        datetime.strptime(visit_date, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date format. Please use YYYY-MM-DD format.\n"
            "Example: 2024-01-20"
        )
        return
    
    if ticket_manager.schedule_technician_visit(ticket_id, technician_name, technician_phone, visit_date, visit_time):
        # Update status
        ticket_manager.update_status(ticket_id, "Technician Scheduled")
        
        # Notify customer
        customer_id = ticket['user_id']
        try:
            customer_message = get_text(customer_id, "technician_scheduled",
                visit_date,
                visit_time,
                technician_name,
                technician_phone
            )
            
            customer_message += "\n\n" + get_text(customer_id, "technician_note")
            
            await context.bot.send_message(
                chat_id=customer_id,
                text=customer_message,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Check Ticket Status", callback_data=f"check_ticket_{ticket_id}")]
                ]),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify customer: {e}")
        
        # Confirm to admin
        await update.message.reply_text(
            get_text(user_id, "visit_scheduled",
                ticket_id,
                technician_name,
                visit_date,
                visit_time
            ),
            parse_mode='Markdown'
        )
        
        # Notify all admins
        for admin_id in ADMIN_USER_IDS:
            if admin_id != user_id:
                try:
                    admin_message = f"🔧 *Technician Visit Scheduled*\n\n"
                    admin_message += f"🎫 Ticket: `{ticket_id}`\n"
                    admin_message += f"👤 Customer: {ticket['user_name']}\n"
                    admin_message += f"📱 Phone: {ticket.get('phone', 'Not provided')}\n"
                    admin_message += f"👨‍🔧 Technician: {technician_name}\n"
                    admin_message += f"📱 Tech Phone: {technician_phone}\n"
                    admin_message += f"📅 Date: {visit_date}\n"
                    admin_message += f"⏰ Time: {visit_time}"
                    
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin: {e}")
        
        user_sessions[user_id] = {"step": "main_menu"}
    else:
        await update.message.reply_text("❌ Failed to schedule visit. Please try again.")

async def process_technician_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process technician verification input from admin"""
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text(user_id, "unauthorized"))
        return
    
    ticket_id = session.get("verify_ticket_id")
    if not ticket_id:
        await update.message.reply_text("❌ No ticket selected.")
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await update.message.reply_text("❌ Ticket not found.")
        return
    
    text = update.message.text.strip()
    
    # Parse: Findings | Verified Issue | Materials | Material Cost | Service Fee
    parts = text.split('|')
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Please provide at least:\n"
            "`Findings | Verified Issue`\n\n"
            "Example: `Power supply faulty | Need power supply board replacement`"
        )
        return
    
    findings = parts[0].strip()
    verified_issue = parts[1].strip()
    materials = parts[2].strip() if len(parts) > 2 else ""
    material_cost = float(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else 0
    service_fee = float(parts[4].strip()) if len(parts) > 4 and parts[4].strip() else BASE_SERVICE_FEE
    
    if ticket_manager.confirm_technician_verification(ticket_id, findings, verified_issue, materials, material_cost, service_fee):
        total = material_cost + service_fee
        
        # Notify customer
        customer_id = ticket['user_id']
        try:
            if material_cost == 0 and service_fee == 0:
                customer_message = f"""✅ *Technician Verification Complete!*

🎫 Ticket: `{ticket_id}`

🔍 *Findings:*
{findings}

📋 *Verified Issue:*
{verified_issue}

💡 *No payment required.* Our technician has provided a free recommendation.

Please follow the advice given above.

🔒 *1-Year Guarantee:* If the same issue recurs, we'll fix it for free!

⭐ *After following the recommendation, please rate your experience!*"""
                
                keyboard = [
                    [InlineKeyboardButton("📋 Check Ticket Status", callback_data=f"check_ticket_{ticket_id}")],
                    [InlineKeyboardButton("⭐ Rate Service", callback_data="rate_service")]
                ]
            else:
                customer_message = get_text(customer_id, "technician_confirmation",
                    ticket_id,
                    findings,
                    verified_issue,
                    materials if materials else "None",
                    material_cost,
                    service_fee,
                    total
                )
                
                keyboard = [
                    [InlineKeyboardButton("💳 Make Payment", callback_data="make_payment")],
                    [InlineKeyboardButton("📋 Check Ticket Status", callback_data=f"check_ticket_{ticket_id}")]
                ]
            
            await context.bot.send_message(
                chat_id=customer_id,
                text=customer_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify customer: {e}")
        
        # Confirm to admin
        admin_response = f"""✅ *Technician Verification Complete!*

🎫 Ticket: `{ticket_id}`
👤 Customer: {ticket['user_name']}

🔍 *Findings:*
{findings}

📋 *Verified Issue:*
{verified_issue}

📦 *Materials:* {materials if materials else "None"}
💰 *Material Cost:* {material_cost} ETB
🔧 *Service Fee:* {service_fee} ETB
💵 *Total:* {total} ETB

✅ Customer has been notified."""
        
        await update.message.reply_text(
            admin_response,
            parse_mode='Markdown'
        )
        
        user_sessions[user_id] = {"step": "main_menu"}
    else:
        await update.message.reply_text("❌ Failed to confirm verification. Please try again.")

async def process_suggestion_provision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process suggestion provision from admin"""
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text(user_id, "unauthorized"))
        return
    
    ticket_id = session.get("suggestion_ticket_id")
    if not ticket_id:
        await update.message.reply_text("❌ No ticket selected.")
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await update.message.reply_text("❌ Ticket not found.")
        return
    
    suggestion = update.message.text.strip()
    
    if not suggestion:
        await update.message.reply_text("❌ Please provide a suggestion.")
        return
    
    if ticket_manager.provide_suggestion(ticket_id, suggestion):
        # Update status
        ticket_manager.update_status(ticket_id, "Suggestion Provided")
        
        # Notify customer
        customer_id = ticket['user_id']
        try:
            customer_message = get_text(customer_id, "suggestion_provided",
                ticket_id,
                suggestion
            )
            
            await context.bot.send_message(
                chat_id=customer_id,
                text=customer_message,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Check Ticket Status", callback_data=f"check_ticket_{ticket_id}")],
                    [InlineKeyboardButton("⭐ Rate Service", callback_data="rate_service")]
                ]),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify customer: {e}")
        
        # Confirm to admin
        await update.message.reply_text(
            f"✅ *Suggestion Provided!*\n\n"
            f"🎫 Ticket: `{ticket_id}`\n"
            f"👤 Customer: {ticket.get('user_name', 'Unknown')}\n\n"
            f"💡 *Suggestion:*\n{suggestion}\n\n"
            f"✅ Customer has been notified.",
            parse_mode='Markdown'
        )
        
        user_sessions[user_id] = {"step": "main_menu"}
    else:
        await update.message.reply_text("❌ Failed to provide suggestion. Please try again.")

async def process_screenshot_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process screenshot upload from customer"""
    global SCREENSHOTS_DIR
    
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})
    
    ticket_id = session.get("payment_ticket_id")
    if not ticket_id:
        await update.message.reply_text("❌ No payment in progress.")
        return
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await update.message.reply_text("❌ Ticket not found.")
        return
    
    # Create screenshots directory if not exists
    if not os.path.exists(SCREENSHOTS_DIR):
        try:
            os.makedirs(SCREENSHOTS_DIR, mode=0o777)
        except Exception as e:
            logger.error(f"Failed to create screenshots directory: {e}")
            SCREENSHOTS_DIR = os.path.join(os.getcwd(), "payment_screenshots")
            if not os.path.exists(SCREENSHOTS_DIR):
                os.makedirs(SCREENSHOTS_DIR, mode=0o777)
    
    try:
        file_name = None
        
        if update.message.photo:
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = os.path.join(SCREENSHOTS_DIR, f"payment_{ticket_id}_{timestamp}.jpg")
            
            await photo_file.download_to_drive(file_name)
            
        elif update.message.document:
            document = update.message.document
            file = await document.get_file()
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = os.path.join(SCREENSHOTS_DIR, f"payment_{ticket_id}_{timestamp}.pdf")
            
            await file.download_to_drive(file_name)
        
        else:
            await update.message.reply_text("❌ Unsupported file type. Please upload a photo or PDF.")
            return
        
        if not file_name or not os.path.exists(file_name):
            await update.message.reply_text("❌ Failed to save screenshot. Please try again.")
            return
        
        # Update ticket
        ticket_manager.update_payment(
            ticket_id=ticket_id,
            payment_method="screenshot",
            payment_reference=f"Screenshot: {os.path.basename(file_name)}",
            amount=ticket.get("payment_amount", 0),
            verified=False,
            verification_data=json.dumps({
                "screenshot_file": file_name,
                "uploaded_at": datetime.now().isoformat()
            })
        )
        ticket_manager.update_status(ticket_id, "Awaiting Verification")
        
        await update.message.reply_text(
            f"✅ *Screenshot Received!*\n\n"
            f"🎫 *Ticket:* `{ticket_id}`\n"
            f"💰 *Amount:* {ticket.get('payment_amount', 0)} ETB\n\n"
            f"⏳ Our team will verify your payment within 1-2 hours.\n\n"
            f"Thank you for your patience! 🙏",
            parse_mode='Markdown'
        )
        
        # Notify admins with the screenshot
        for admin_id in ADMIN_USER_IDS:
            try:
                with open(file_name, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=f,
                        filename=os.path.basename(file_name),
                        caption=f"📸 *New Payment Screenshot*\n\n"
                                f"🎫 Ticket: `{ticket_id}`\n"
                                f"👤 Customer: {ticket.get('user_name', 'Unknown')}\n"
                                f"📱 Phone: {ticket.get('phone', 'Not provided')}\n"
                                f"💰 Amount: {ticket.get('payment_amount', 0)} ETB\n"
                                f"📅 Submitted: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                                f"⚠️ *Action Required:* Verify this payment.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ Verify Payment", callback_data=f"admin_verify_payment_{ticket_id}")],
                            [InlineKeyboardButton("❌ Reject Payment", callback_data=f"admin_reject_payment_{ticket_id}")]
                        ]),
                        parse_mode='Markdown'
                    )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")
        
        user_sessions[user_id] = {"step": "main_menu"}
        
    except Exception as e:
        logger.error(f"Error uploading screenshot: {e}")
        await update.message.reply_text(
            "❌ *Error Uploading Screenshot*\n\n"
            "Please try again or use a different payment method.",
            parse_mode='Markdown'
        )

async def show_ticket_status(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str) -> None:
    """Show ticket status"""
    query = update.callback_query
    user_id = query.from_user.id
    
    ticket = ticket_manager.get_ticket(ticket_id)
    if not ticket:
        await query.edit_message_text(
            get_text(user_id, "no_ticket_found", ticket_id)
        )
        return
    
    status_emoji = {
        "Pending Review": get_text(user_id, "status_pending_review"),
        "Technician Scheduled": get_text(user_id, "status_technician_scheduled"),
        "Awaiting Payment": get_text(user_id, "status_awaiting_payment"),
        "Awaiting Verification": get_text(user_id, "status_awaiting_verification"),
        "Payment Confirmed": get_text(user_id, "status_payment_confirmed"),
        "In Progress": get_text(user_id, "status_in_progress"),
        "Completed": get_text(user_id, "status_completed"),
        "Suggestion Provided": get_text(user_id, "status_suggestion_provided"),
        "Cancelled": get_text(user_id, "status_cancelled")
    }.get(ticket['status'], get_text(user_id, "status_default"))
    
    location_display = ticket.get('location', get_text(user_id, "location_not_provided"))
    if location_display and location_display != "Not shared" and location_display != "Not provided" and location_display.startswith("http"):
        location_display = f"[{get_text(user_id, 'view_on_map')}]({location_display})"
    
    service_type = ticket.get('service_type', 'technician')
    service_display = get_localized_service_type(service_type, user_id)
    
    rating_display = get_rating_display(ticket.get('rating'))
    
    payment_info = ""
    if ticket.get('quote_provided', False):
        if ticket.get('payment_amount', 0) > 0:
            payment_info = f"💰 *Amount:* {ticket.get('payment_amount', 0)} ETB\n"
            payment_info += f"💳 *Payment Status:* {ticket.get('payment_status', 'Pending')}\n"
        else:
            payment_info = "💡 *Suggestion Provided* - No payment required"
    else:
        if service_type == "suggestion":
            payment_info = "⏳ Waiting for suggestion from our team"
        else:
            payment_info = "⏳ Waiting for technician verification"
    
    assigned_text = ""
    if ticket.get('assigned_to'):
        assigned_text = get_text(user_id, "assigned_to", ticket['assigned_to'])
    
    estimated_text = ""
    if ticket.get('estimated_visit'):
        estimated_text = get_text(user_id, "estimated_visit", ticket['estimated_visit'])
    
    guarantee_text = ""
    if ticket['status'] == 'Completed':
        guarantee_text = get_guarantee_status(ticket)
    elif ticket['status'] == 'Payment Confirmed' or ticket['status'] == 'In Progress':
        guarantee_text = "🔒 Guarantee will be active after service completion"
    else:
        guarantee_text = "🔒 Guarantee not yet applicable"
    
    next_steps = {
        "Pending Review": "Our team will review your request and respond shortly.",
        "Technician Scheduled": "A technician has been scheduled to visit and verify the issue.",
        "Awaiting Payment": "Please make payment to proceed with the service.",
        "Awaiting Verification": "Your payment is being verified. Please wait.",
        "Payment Confirmed": "We will assign a technician and schedule your service.",
        "In Progress": "Your service is in progress.",
        "Completed": "Service completed. Thank you for choosing Glorious PLC!\n\n🔒 Your 1-year guarantee is now active!\n\n⭐ Please rate your experience using the 'Rate Service' button!",
        "Suggestion Provided": "Please follow the suggestion provided.\n\n⭐ After following the suggestion, please rate your experience!",
    }.get(ticket['status'], "Please contact support for more information.")
    
    status_text = get_text(user_id, "ticket_status",
        ticket['ticket_id'],
        status_emoji,
        ticket['status'],
        ticket['user_name'],
        ticket.get('phone', get_text(user_id, "location_not_provided")),
        location_display,
        ticket['category_name'],
        ticket['brand_name'],
        ticket['issue_name'],
        service_display,
        payment_info,
        ticket['created_at'].split('T')[0],
        assigned_text,
        estimated_text,
        rating_display,
        guarantee_text,
        next_steps
    )
    
    keyboard = [[InlineKeyboardButton(get_text(user_id, "back_to_menu"), callback_data="back_to_main")]]
    
    if ticket['status'] in ["Awaiting Payment", "Awaiting Verification"] and ticket.get('payment_amount', 0) > 0:
        keyboard.insert(0, [InlineKeyboardButton(get_text(user_id, "payment"), callback_data="make_payment")])
    
    if ticket['status'] == "Completed" and ticket.get('rating') is None:
        keyboard.insert(0, [InlineKeyboardButton("⭐ Rate Service", callback_data="rate_service")])
    
    await query.edit_message_text(
        status_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

# ==================== SETUP BOT FUNCTION ====================

def setup_bot():
    """Setup bot application with all handlers"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.LOCATION, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.Document.IMAGE | filters.Document.PDF, handle_message))
    
    return application

# ==================== MAIN FUNCTION ====================

def main():
    """Main function to run the bot"""
    global SCREENSHOTS_DIR
    
    # The directories are already set up at the top of the file
    if not os.path.exists(SCREENSHOTS_DIR):
        try:
            os.makedirs(SCREENSHOTS_DIR, mode=0o777)
            print(f"📁 Created screenshots directory: {SCREENSHOTS_DIR}")
        except Exception as e:
            print(f"⚠️ Could not create directory: {e}")
            SCREENSHOTS_DIR = os.path.join(os.getcwd(), "payment_screenshots")
            if not os.path.exists(SCREENSHOTS_DIR):
                os.makedirs(SCREENSHOTS_DIR, mode=0o777)
    
    # Load tickets
    all_tickets = ticket_manager.get_all_tickets()
    print(f"📂 Loaded {len(all_tickets)} tickets from {TICKETS_FILE}")
    
    # Create application
    application = setup_bot()
    
    # Print startup info
    env = "VERCEL" if os.environ.get('VERCEL') else "RENDER" if os.environ.get('RENDER') else "LOCAL"
    print(f"🤖 {COMPANY_NAME} Support Bot is running...")
    print(f"🌍 Environment: {env}")
    print(f"🐍 Python Version: {sys.version}")
    print("🌐 Languages supported: English and Amharic")
    print("💡 Service Options: Suggestion Only OR Technician Required")
    print("⭐ Rating System: YES - Customers can rate after service completion")
    print("💰 Payment flow: Customer Request → Service Type → Response → Payment (if needed)")
    print("🔧 Technician Verification: YES - Customer pays only after verification")
    print("🔒 1-Year Guarantee on all repairs")
    print("📸 Payment Screenshot Support: YES")
    print("📅 Appointment Scheduling: YES")
    print("🔎 Search Tickets: YES")
    print("⏰ Auto-Reminders: YES")
    if SCREENSHOTS_DIR:
        print(f"📁 Screenshots saved to: {SCREENSHOTS_DIR}")
    print("📊 Admin Panel: Reply Keyboard with all admin functions")
    print("Press Ctrl+C to stop")
    
    # Check if running on Vercel
    if os.environ.get('VERCEL'):
        # Webhook mode for Vercel
        print("🚀 Starting bot in WEBHOOK mode for Vercel")
        # For Vercel, we don't run polling - the webhook endpoint will handle updates
        # The application is exported for Vercel to use
        return application
    else:
        # Polling mode for local development
        print("🚀 Starting bot in POLLING mode...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

# ==================== VERCEL ENTRY POINT ====================

# This is the entry point for Vercel serverless functions
# Export the application and handlers for Vercel
app = None

def get_app():
    """Get or create the bot application for Vercel"""
    global app
    if app is None:
        app = main()  # This will return the application in Vercel mode
    return app

# For local testing
if __name__ == "__main__":
    main()