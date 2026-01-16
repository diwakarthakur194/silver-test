"""
SMART TEST GENERATOR - STREAMLIT VERSION (ENHANCED ULTIMATE EDITION v9)
Features Included:
- ALL ORIGINAL FEATURES (Preserved)
- MOVED CONTENT VERIFICATION (To Configure Page)
- INDIVIDUAL CLEAR BUTTONS (Files/Text/Images)
- CUSTOM UI COLORS (Light Background, Dark Buttons)
- DIRECT TEXT TO AI (No processing on paste)
"""

import streamlit as st
from google import genai
from google.genai import types
import json, time, io, os, base64, re
from datetime import datetime
# from pypdf import PdfReader <-- Disabled as per request
from PIL import Image
# import pytesseract  <-- Commented out for Standalone App Compatibility
import docx
import pandas as pd

# =============================================================================
# 0. TESSERACT CONFIGURATION (DISABLED FOR PORTABLE APP)
# =============================================================================
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# =============================================================================
# 1. CONFIGURATION
# =============================================================================
API_KEY = "AIzaSyDGJgLItTQngvzT-M2Ie6pCIPWxUbZWl0g"

if not API_KEY:
    st.error("⚠️ No API key found!")
    st.stop()

try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"Failed to initialize AI client: {e}")
    st.stop()

# =============================================================================
# 2. SMART MODEL HANDLER
# =============================================================================
@st.cache_resource(ttl=3600)
def get_working_models():
    try:
        all_models = list(client.models.list())
        valid = []
        
        for m in all_models:
            model_id = m.name.replace("models/", "")
            if "gemini" in model_id.lower() and "embedding" not in model_id.lower():
                valid.append(model_id)
        
        valid.sort(key=lambda x: (
            0 if "flash" in x and "exp" not in x else
            1 if "flash" in x else
            2 if "pro" in x and "vision" in x else
            3 if "pro" in x else 4
        ))
        
        return valid if valid else ["gemini-1.5-flash", "gemini-1.5-pro"]
    except:
        return ["gemini-1.5-flash", "gemini-1.5-pro"]

AVAILABLE_MODELS = get_working_models()

if 'last_working_model' not in st.session_state:
    st.session_state.last_working_model = AVAILABLE_MODELS[0]

def generate_with_smart_retry(prompt, media=None, expect_json=True, max_retries=2):
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if expect_json else "text/plain",
        temperature=0.3
    )
    
    contents = []
    if media:
        contents.append(media)
    contents.append(prompt)
    
    if media:
        models_to_try = [m for m in AVAILABLE_MODELS if "vision" in m or "flash" in m]
        if not models_to_try: models_to_try = AVAILABLE_MODELS
    else:
        models_to_try = [st.session_state.last_working_model] + \
                        [m for m in AVAILABLE_MODELS if m != st.session_state.last_working_model]
    
    for attempt in range(max_retries):
        for model in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )
                
                text = response.text
                
                if expect_json:
                    clean = text.replace("```json", "").replace("```", "").strip()
                    result = json.loads(clean)
                    st.session_state.last_working_model = model
                    return result
                
                st.session_state.last_working_model = model
                return text
                
            except json.JSONDecodeError as e:
                continue
            except Exception as e:
                continue
        
        time.sleep(1)
    
    return None

# =============================================================================
# 3. FILE EXTRACTION (UPDATED: FIXED PART.FROM_BYTES ERROR)
# =============================================================================
def extract_text_from_file(file):
    try:
        # CHECK SIZE LIMIT (20MB) to prevent AI errors
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 20 * 1024 * 1024: # 20MB Limit
            st.error(f"⚠️ File {file.name} is too large (>20MB). AI cannot process it.")
            return None, 0

        file_ext = file.name.split('.')[-1].lower()
        
        if file_ext == 'pdf':
            # DIRECT AI PROCESSING - FIXED ERROR HERE
            try:
                pdf_bytes = file.read()
                
                # FIXED: Use keyword arguments for from_bytes
                pdf_part = types.Part.from_bytes(
                    data=pdf_bytes, 
                    mime_type="application/pdf"
                )
                
                # Prompt the AI to read the file directly
                prompt = "Read this PDF document and extract all the text content from it verbatim. Do not summarize."
                
                # Use the existing AI generator
                text_content = generate_with_smart_retry(prompt, media=pdf_part, expect_json=False)
                
                if not text_content:
                    return "Error: AI could not read this PDF.", 0
                    
                return text_content, 1
            except Exception as e:
                st.error(f"AI Processing failed: {str(e)}")
                return None, 0
        
        elif file_ext in ['docx', 'doc']:
            try:
                doc = docx.Document(file)
                text = "\n".join([para.text for para in doc.paragraphs])
                return text, len(doc.paragraphs)
            except Exception as e:
                st.error(f"Word extraction failed: {str(e)}")
                return None, 0
        
        elif file_ext in ['txt', 'md']:
            try:
                text = file.read().decode('utf-8')
                return text, len(text.split('\n'))
            except:
                text = file.read().decode('latin-1')
                return text, len(text.split('\n'))
        
        else:
            return None, 0
            
    except Exception as e:
        st.error(f"File extraction error: {str(e)}")
        return None, 0

# NEW: Image preprocessing function
def auto_rotate_image(image):
    """Auto-rotate image based on EXIF data"""
    try:
        from PIL import ImageOps
        return ImageOps.exif_transpose(image)
    except:
        return image

# NEW: Get file size
def get_file_size(file):
    """Return file size in human readable format"""
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

# =============================================================================
# 4. SESSION STATE INITIALIZATION
# =============================================================================
def init_session_state():
    defaults = {
        'step': 'upload',
        'questions': [],
        'answers': {},
        'flagged': set(),
        'uploaded_text': "",
        # NEW: Separate storage for individual clear functionality
        'text_part_files': "",
        'text_part_paste': "",
        'text_part_images': "",
        'refined_text': "",
        'diff_view_html': "",
        'detected_mistakes': [],
        'custom_instructions': "",
        'enable_correction': True,
        'correction_level': 'Full Correction',
        'show_viewer': False,
        'current_q_index': 0,
        'test_duration': 30,
        'test_start_time': 0,
        'test_paused': False,
        'pause_start_time': 0,
        'total_pause_duration': 0,
        'difficulty': 'medium',
        'results': None,
        'test_history': [],
        'config': {},
        'uploader_key': 0,
        'custom_instruction_favorites': [],
        'file_previews': {},
        'selected_files': [],
        'question_generation_progress': [],
        'question_time_spent': {},
        'answer_versions': {},
        'content_sections': [],
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# Helper to reconstruct full text from parts
def update_full_text():
    st.session_state.uploaded_text = (
        st.session_state.text_part_files + 
        st.session_state.text_part_paste + 
        st.session_state.text_part_images
    )

# =============================================================================
# 5. TIMER LOGIC (ENHANCED WITH PAUSE/RESUME)
# =============================================================================
def get_remaining_time():
    if st.session_state.test_start_time == 0:
        return st.session_state.test_duration * 60
    
   # FIX: Correct pause calculation
    now = time.time()
    total_elapsed = now - st.session_state.test_start_time
    
    if st.session_state.test_paused:
        current_pause = now - st.session_state.pause_start_time
        effective_pause = st.session_state.total_pause_duration + current_pause
    else:
        effective_pause = st.session_state.total_pause_duration
        
    elapsed = total_elapsed - effective_pause
    
    remaining = (st.session_state.test_duration * 60) - elapsed
    return max(0, int(remaining))

def format_time(seconds):
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:02d}:{secs:02d}"

def check_time_warnings(remaining):
    if remaining <= 60:
        return "🚨 1 minute remaining!"
    elif remaining <= 300:
        return "⚠️ 5 minutes remaining!"
    return None

# NEW: Pause/Resume functions
def toggle_pause():
    if st.session_state.test_paused:
        # Resume
        pause_duration = time.time() - st.session_state.pause_start_time
        st.session_state.total_pause_duration += pause_duration
        st.session_state.test_paused = False
    else:
        # Pause
        st.session_state.pause_start_time = time.time()
        st.session_state.test_paused = True

def get_time_spent_on_question(q_index):
    """Calculate time spent on specific question"""
    return st.session_state.question_time_spent.get(q_index, 0)

# =============================================================================
# 6. EXPORT FUNCTIONALITY
# =============================================================================
def export_to_csv(results):
    data = []
    for i, e in enumerate(results['evals']):
        data.append({
            'Question_No': i + 1,
            'Question': e['question'],
            'Type': e['type'],
            'Your_Answer': e.get('user_ans', 'No Answer'),
            'Correct_Answer': e.get('correctAnswer', 'N/A'),
            'Score': e['score'],
            'Max_Marks': e['marks'],
            'Feedback': e['feedback'],
            'Time_Spent_Seconds': e.get('time_spent', 0)
        })
    
    df = pd.DataFrame(data)
    return df.to_csv(index=False)

def export_question_paper():
    content = f"# TEST PAPER\n\n"
    content += f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    content += f"**Duration:** {st.session_state.test_duration} minutes\n"
    content += f"**Total Marks:** {sum(q['marks'] for q in st.session_state.questions)}\n\n"
    content += "---\n\n"
    
    for i, q in enumerate(st.session_state.questions):
        content += f"## Question {i+1} ({q['marks']} marks)\n\n"
        content += f"{q['question']}\n\n"
        
        if q['type'] == 'mcq':
            for opt in q['options']:
                content += f"- {opt}\n"
            content += "\n"
        elif q['type'] == 'short':
            content += "_" * 50 + "\n\n"
        elif q['type'] == 'long':
            content += "_" * 50 + "\n" + "_" * 50 + "\n\n"
        
        content += "---\n\n"
    
    return content

def export_answer_key():
    content = f"# ANSWER KEY\n\n"
    content += f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    content += "---\n\n"
    
    for i, q in enumerate(st.session_state.questions):
        content += f"## Question {i+1}\n\n"
        content += f"**Question:** {q['question']}\n\n"
        
        if q['type'] == 'mcq':
            content += f"**Correct Answer:** {q['correctAnswer']}\n\n"
        else:
            content += f"**Sample Answer:** (Subjective - teacher evaluation required)\n\n"
        
        content += "---\n\n"
    
    return content

# =============================================================================
# 7. UI STYLING (ENHANCED)
# =============================================================================
st.set_page_config(
    page_title="Smart Test Generator Pro",
    page_icon="📝",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# REPLACED COLORS AS REQUESTED
st.markdown("""
    <style>
    /* Main Background Light */
    .stApp {
        background-color: #f7f9fc;
    }
    /* Section Background */
    .main .block-container {
        background-color: #ffffff;
        padding: 3rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    
    /* Buttons Darker than section */
    .stButton>button { 
        width: 100%; 
        border-radius: 8px; 
        height: 3em; 
        font-weight: 600;
        background-color: #2c3e50 !important; /* Dark Blue-Grey */
        color: white !important;
        border: none !important;
    }
    
    /* Hover state for buttons */
    .stButton>button:hover {
        background-color: #34495e !important;
    }

    /* Style for disabled buttons to look lighter */
    .stButton>button:disabled {
        background-color: #95a5a6 !important;
        color: #ecf0f1 !important;
        cursor: not-allowed;
    }
    
    /* Click to view button specific color */
    .view-btn {
        background-color: #8e44ad !important;
    }

    .question-card, .question-card h3, .question-card p { 
        background-color: #f8f9fa; 
        color: #000000 !important; 
        padding: 25px; 
        border-radius: 12px; 
        border-left: 5px solid #6c5ce7; 
        margin: 20px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .timer-box { 
        font-size: 24px; 
        font-weight: bold; 
        color: #e74c3c; 
        text-align: center; 
        border: 3px solid #e74c3c; 
        padding: 15px; 
        border-radius: 10px; 
        background: #fff5f5;
    }
    .timer-warning {
        background: #fff3cd !important;
        border-color: #ffc107 !important;
        color: #856404 !important;
    }
    .timer-danger {
        background: #f8d7da !important;
        border-color: #dc3545 !important;
        color: #721c24 !important;
        animation: pulse 1s infinite;
    }
    .timer-paused {
        background: #d1ecf1 !important;
        border-color: #17a2b8 !important;
        color: #0c5460 !important;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    .flag-button {
        background: #ffc107 !important;
        color: #000 !important;
    }
    .progress-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
        gap: 8px;
        margin: 20px 0;
    }
    .progress-item {
        padding: 8px;
        text-align: center;
        border-radius: 5px;
        cursor: pointer;
        font-weight: bold;
        font-size: 14px;
    }
    .answered { background: #d4edda; border: 2px solid #28a745; }
    .flagged { background: #fff3cd; border: 2px solid #ffc107; }
    .unanswered { background: #f8d7da; border: 2px solid #dc3545; }
    .current { background: #cfe2ff; border: 3px solid #0d6efd; }
    
    .diff-container {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 8px;
        font-family: monospace;
        line-height: 1.6;
        color: #333;
    }
    .diff-del {
        background-color: #ffeef0;
        color: #b31d28;
        text-decoration: line-through;
        padding: 2px 4px;
        border-radius: 4px;
    }
    .diff-add {
        background-color: #e6ffed;
        color: #22863a;
        font-weight: bold;
        padding: 2px 4px;
        border-radius: 4px;
    }
    
    /* NEW: File preview styles */
    .file-preview-card {
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background: #f8f9fa;
    }
    
    /* NEW: Highlighted answer parts */
    .answer-correct {
        background-color: #d4edda;
        padding: 2px 4px;
        border-radius: 3px;
        border-left: 3px solid #28a745;
    }
    .answer-incorrect {
        background-color: #f8d7da;
        padding: 2px 4px;
        border-radius: 3px;
        border-left: 3px solid #dc3545;
    }
    .answer-partial {
        background-color: #fff3cd;
        padding: 2px 4px;
        border-radius: 3px;
        border-left: 3px solid #ffc107;
    }
    
    /* NEW: Question generation preview */
    .gen-preview {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        animation: slideIn 0.3s ease-out;
    }
    @keyframes slideIn {
        from { transform: translateX(-20px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 8. KEYBOARD SHORTCUTS (NEW)
# =============================================================================
def add_keyboard_shortcuts():
    """Add keyboard navigation for test"""
    if st.session_state.step == 'test':
        st.markdown("""
        <script>
        document.addEventListener('keydown', function(e) {
            # Prevent default only for our shortcuts
            const isOurShortcut = (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || 
                                   e.key === 'f' || e.key === 's') && !e.shiftKey && !e.ctrlKey && !e.altKey;
            
            // FIX: stricter check for active elements to prevent typing interference
            const activeEl = document.activeElement;
            const tagName = activeEl.tagName;
            const isInput = tagName === 'INPUT' || tagName === 'TEXTAREA' || activeEl.isContentEditable;

            if (isOurShortcut && !isInput) {
                
                if (e.key === 'ArrowLeft') {
                    e.preventDefault();
                    const prevBtn = document.querySelector('button[kind="secondary"]');
                    if (prevBtn && !prevBtn.disabled) prevBtn.click();
                }
                else if (e.key === 'ArrowRight') {
                    e.preventDefault();
                    const nextBtns = document.querySelectorAll('button[kind="secondary"]');
                    if (nextBtns.length > 1) nextBtns[nextBtns.length-1].click();
                }
                else if (e.key === 'f') {
                    e.preventDefault();
                    const flagBtn = document.querySelector('button[data-testid*="flag"]');
                    if (flagBtn) flagBtn.click();
                }
                else if (e.key === 's') {
                    e.preventDefault();
                    const submitBtn = document.querySelector('button[kind="primary"]');
                    if (submitBtn) {
                        if (confirm('Submit test now?')) submitBtn.click();
                    }
                }
            }
        });
        </script>
        """, unsafe_allow_html=True)

# =============================================================================
# 9. STEP 1: UPLOAD (ENHANCED WITH FILE PREVIEW)
# =============================================================================
def reset_application():
    st.session_state.uploaded_text = ""
    st.session_state.text_part_files = ""
    st.session_state.text_part_paste = ""
    st.session_state.text_part_images = ""
    st.session_state.refined_text = ""
    st.session_state.detected_mistakes = []
    st.session_state.questions = []
    st.session_state.answers = {}
    st.session_state.results = None
    st.session_state.custom_instructions = ""
    st.session_state.diff_view_html = ""
    st.session_state.show_viewer = False
    st.session_state.file_previews = {}
    st.session_state.selected_files = []
    st.session_state.uploader_key += 1

def toggle_viewer():
    st.session_state.show_viewer = not st.session_state.show_viewer

# NEW: Individual Clear Functions
def clear_files_section():
    st.session_state.text_part_files = ""
    st.session_state.selected_files = [] # FIX: Clear the tracking list
    st.session_state.uploader_key += 1
    update_full_text()

def clear_paste_section():
    st.session_state.text_part_paste = ""
    update_full_text()

def clear_images_section():
    st.session_state.text_part_images = ""
    update_full_text()

if st.session_state.step == 'upload':
    st.markdown("# 📝 Smart Test Generator Pro")
    st.caption(f"🤖 AI Engine: {len(AVAILABLE_MODELS)} models available | Using: {st.session_state.last_working_model}")
    
    # NEW: How it Works Section (To prevent confusion)
    with st.expander("📖 How it Works (Click to Read)", expanded=True):
        st.markdown("""
        1.  **Upload Content:** Upload PDFs, Images, or Paste Text below.
        2.  **AI Processing:** The system will read your files automatically (Limit: 20MB per file).
        3.  **Generate Test:** Review the extracted content, choose difficulty, and start your exam!
        """)

    # Top control bar
    col_ctrl_1, col_ctrl_2, col_ctrl_3 = st.columns([1.5, 1.5, 1])
    
    with col_ctrl_1:
        # NEW: Enhanced correction level selector
        st.session_state.correction_level = st.selectbox(
            "🔧 Correction Level",
            options=[
                'Grammar Only',
                'Grammar + Spelling', 
                'Grammar + Facts',
                'Full Correction'
            ],
            index=3,
            help="Choose what type of corrections AI should make"
        )
        
    # NOTE: Moved Content Verification button to next step as requested
    with col_ctrl_2:
        pass # Empty placeholder to maintain layout
             
    with col_ctrl_3:
        st.button("🗑️ Clear All", on_click=reset_application, help="Wipe all data.", use_container_width=True)

    # NOTE: Removed Content Verification viewer from here as requested

    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📁 Upload Documents", "✍️ Paste Text", "🖼️ Upload Images (AI)"])
    
    # TAB 1: File Upload (Updated for PDF size check & Direct AI)
    with tab1:
        # Layout for Clear Button inside tab
        c_head, c_clear = st.columns([4, 1])
        with c_head:
            st.info("📄 Upload PDF, DOCX, TXT. AI will extract text.")
        with c_clear:
            st.button("Clear Files", on_click=clear_files_section, use_container_width=True)

        uploaded_files = st.file_uploader(
            "Choose files", 
            type=['pdf', 'docx', 'txt', 'md'], 
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}"
        )
        
        if uploaded_files:
            for file in uploaded_files:
                if file.name not in st.session_state.selected_files:
                    with st.spinner(f"AI is reading {file.name}..."):
                        text, pages = extract_text_from_file(file)
                        if text:
                            # Append to specific file part
                            st.session_state.text_part_files += f"\n\n--- From {file.name} ---\n\n{text}"
                            st.session_state.selected_files.append(file.name)
                            st.success(f"✅ Loaded {file.name} ({get_file_size(file)})")
            update_full_text()

    # TAB 2: Text Paste
    with tab2:
        # Layout for Clear Button inside tab
        c_head, c_clear = st.columns([4, 1])
        with c_head:
            st.info("✍️ Paste your content below.")
        with c_clear:
            st.button("Clear Text", on_click=clear_paste_section, use_container_width=True)

        
        # DIRECT TEXT INPUT - Using Callback to fix race condition
        def on_text_paste_change():
            update_full_text()

        st.text_area(
            "Paste text content here...",
            key="text_part_paste", # Binds directly to session state
            height=200,
            placeholder="Paste text...",
            on_change=on_text_paste_change
        )
    
    # TAB 3: Image Upload (ENHANCED with OCR quality and auto-rotate)
    with tab3:
        # Layout for Clear Button inside tab
        c_head, c_clear = st.columns([4, 1])
        with c_head:
            st.info("📸 Upload up to 10 images. AI will extract text.")
        with c_clear:
            st.button("Clear Images", on_click=clear_images_section, use_container_width=True)
        
        # NEW: OCR Settings
        col_ocr1, col_ocr2 = st.columns(2)
        with col_ocr1:
            ocr_quality = st.select_slider(
                "OCR Quality",
                options=['Fast', 'Balanced', 'High Accuracy'],
                value='Balanced',
                help="Higher quality = slower but more accurate"
            )
        with col_ocr2:
            auto_rotate = st.checkbox("Auto-rotate images", value=True, help="Automatically fix image orientation")
        
        image_files = st.file_uploader(
            "Upload images (Max 10)",
            type=['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp'],
            accept_multiple_files=True,
            key=f"img_uploader_{st.session_state.uploader_key}"
        )
        
        if image_files:
            images_to_process = image_files[:10]
            if len(image_files) > 10:
                st.warning(f"⚠️ Limit is 10 images. Processing first 10.")
            
            # NEW: Image preview gallery
            st.markdown("### 🖼️ Image Preview")
            cols = st.columns(min(3, len(images_to_process)))
            selected_images = []
            
            for idx, img_file in enumerate(images_to_process):
                with cols[idx % 3]:
                    try:
                        image_pil = Image.open(img_file)
                        st.image(image_pil, use_column_width=True, caption=img_file.name)
                        if st.checkbox(f"Process this", key=f"img_sel_{idx}", value=True):
                            selected_images.append((idx, img_file))
                    except Exception as e:
                        st.error(f"Error loading {img_file.name}")
                        
            # SMART BUTTON: Disabled until images are selected
            has_images = len(selected_images) > 0
            if st.button(f"🚀 Process {len(selected_images)} Selected Images", 
                         disabled=not has_images,
                         help="Select at least one image to process" if not has_images else "Click to start AI processing"):
                
                progress_bar = st.progress(0)
                
                for i, (idx, img_file) in enumerate(selected_images):
                    with st.spinner(f"Processing {img_file.name}..."):
                        try:
                            image_pil = Image.open(img_file)
                            
                            # NEW: Auto-rotate
                            if auto_rotate:
                                image_pil = auto_rotate_image(image_pil)
                            
                            # Enhanced OCR prompt based on quality
                            quality_instructions = {
                                'Fast': 'Extract text quickly, main content only.',
                                'Balanced': 'Extract all text with good accuracy, preserve formatting.',
                                'High Accuracy': 'Extract ALL text with maximum accuracy. Preserve tables, formatting, mathematical notation, and special characters.'
                            }
                            
                            ocr_prompt = f"""
                            Task: {quality_instructions[ocr_quality]}
                            
                            Instructions:
                            - Preserve formatting (headings, bullets, tables)
                            - Maintain paragraph structure
                            - Keep mathematical notation
                            - Note diagrams/charts (describe them)
                            
                            Return JSON: {{"extracted_text": "full text...", "has_tables": boolean, "has_diagrams": boolean}}
                            """
                            
                            gemini_response = generate_with_smart_retry(ocr_prompt, media=image_pil, expect_json=True)
                            
                            if gemini_response and gemini_response.get('extracted_text'):
                                extracted = gemini_response['extracted_text']
                                
                                # Add metadata
                                metadata = []
                                if gemini_response.get('has_tables'):
                                    metadata.append("Contains tables")
                                if gemini_response.get('has_diagrams'):
                                    metadata.append("Contains diagrams")
                                
                                metadata_str = f" [{', '.join(metadata)}]" if metadata else ""
                                
                                st.session_state.text_part_images += f"\n\n--- From Image {idx+1}: {img_file.name}{metadata_str} ---\n\n{extracted}"
                                st.success(f"✅ Image {idx+1} processed ({len(extracted)} chars).")
                            else:
                                st.error(f"❌ AI failed to process image {idx+1}.")
                        except Exception as e:
                            st.error(f"Error processing {img_file.name}: {str(e)}")
                    progress_bar.progress((i + 1) / len(selected_images))
                
                update_full_text()
                st.success(f"✅ All {len(selected_images)} images processed!")

    st.markdown("---")
    
    # Next button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # SMART BUTTON: Disabled until content is sufficient
        has_content = len(st.session_state.uploaded_text.strip()) >= 50
        
        if st.button("➡️ Next: Final Analysis & Configure", 
                     type="primary", 
                     use_container_width=True,
                     disabled=not has_content,
                     help="Upload content (at least 50 characters) to proceed" if not has_content else "Click to analyze content and configure test"):
            
            # AI Analysis based on correction level
            with st.spinner("🕵️ AI is analyzing content..."):
                
                # NEW: Correction instructions based on selected level
                correction_instructions = {
                    'Grammar Only': "Identify and fix ONLY grammar mistakes. Keep all facts as-is, even if wrong. In 'refined_text', correct grammar only.",
                    'Grammar + Spelling': "Identify and fix grammar and spelling mistakes ONLY. Ignore factual errors. In 'refined_text', correct grammar and spelling.",
                    'Grammar + Facts': "Identify grammar mistakes and FACTUAL errors. In 'refined_text', correct both grammar and facts.",
                    'Full Correction': "Identify ALL errors: grammar, spelling, facts, logic, structure. In 'refined_text', produce the best corrected version."
                }
                
                correction_mode = st.session_state.correction_level
                correction_instruction = correction_instructions[correction_mode]

                analysis_prompt = f"""
                You are an expert editor. Analyze this text.
                
                CORRECTION MODE: {correction_mode}
                Goal: {correction_instruction}
                
                Generate JSON with:
                1. "mistakes": List of specific errors found (based on correction mode)
                2. "refined_text": Final corrected version
                3. "diff_view_markdown": Show changes using '~~deleted~~' and '**added**'
                4. "correction_stats": {{"grammar": count, "spelling": count, "factual": count}}
                
                TEXT TO ANALYZE:
                {st.session_state.uploaded_text[:25000]}
                
                Return ONLY JSON:
                {{
                    "mistakes": ["error 1 description", "error 2 description"],
                    "refined_text": "full corrected text...",
                    "diff_view_markdown": "markdown with changes...",
                    "has_changes": boolean,
                    "correction_stats": {{"grammar": 0, "spelling": 0, "factual": 0}}
                }}
                """
                
                analysis_result = generate_with_smart_retry(analysis_prompt, expect_json=True)
                
                if analysis_result:
                    st.session_state.detected_mistakes = analysis_result.get('mistakes', [])
                    
                    # NEW: Store correction stats
                    if 'correction_stats' not in st.session_state:
                        st.session_state.correction_stats = {}
                    st.session_state.correction_stats = analysis_result.get('correction_stats', {})
                    
                    if analysis_result.get('has_changes', False):
                        st.session_state.refined_text = analysis_result.get('refined_text', st.session_state.uploaded_text)
                        
                        # Convert markdown diff to HTML
                        raw_diff = analysis_result.get('diff_view_markdown', "")
                        html_diff = re.sub(r'~~(.*?)~~', r'<span class="diff-del">\1</span>', raw_diff)
                        html_diff = re.sub(r'\*\*(.*?)\*\*', r'<span class="diff-add">\1</span>', html_diff)
                        st.session_state.diff_view_html = html_diff
                    else:
                        st.session_state.refined_text = st.session_state.uploaded_text
                        st.session_state.diff_view_html = st.session_state.uploaded_text
                        
                    # Logic for show viewer handles in next step now
                else:
                    st.session_state.refined_text = st.session_state.uploaded_text
                    st.session_state.diff_view_html = st.session_state.uploaded_text

            st.session_state.step = 'customize'
            st.rerun()

# =============================================================================
# 10. STEP 2: CUSTOMIZE (ENHANCED WITH TEMPLATES & FAVORITES)
# =============================================================================
elif st.session_state.step == 'customize':
    st.markdown("## ⚙️ Configure Your Test")
    
    # Show correction statistics
    if st.session_state.detected_mistakes:
        correction_mode = st.session_state.correction_level
        stats = st.session_state.get('correction_stats', {})
        
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        with col_stat1:
            st.metric("Total Issues", len(st.session_state.detected_mistakes))
        with col_stat2:
            st.metric("Grammar", stats.get('grammar', 0))
        with col_stat3:
            st.metric("Spelling", stats.get('spelling', 0))
        with col_stat4:
            st.metric("Factual", stats.get('factual', 0))
        
        # MOVED CONTENT VERIFICATION SECTION HERE
        with st.expander(f"👀 View {len(st.session_state.detected_mistakes)} Detected Issues", expanded=True):
            
            # Colored button to toggle verification view
            if st.button("🎨 Click to view content issues", key="toggle_verify", use_container_width=True):
                toggle_viewer()
            
            if st.session_state.show_viewer:
                st.markdown("---")
                with st.container():
                    st.markdown("### 📝 Content Verification")
                    
                    tab_v1, tab_v2 = st.tabs(["🔍 Visual Diff (Changes)", "✏️ Edit Final Text"])
                    
                    with tab_v1:
                        st.caption("Red = Removed/Wrong. Green = Added/Corrected.")
                        if st.session_state.diff_view_html:
                            st.markdown(f'<div class="diff-container">{st.session_state.diff_view_html}</div>', unsafe_allow_html=True)
                        else:
                            st.info("No changes were made by the AI.")
                    
                    with tab_v2:
                        st.caption("This text will be used to generate the test. Edit it if needed.")
                        st.session_state.refined_text = st.text_area(
                            "Final Content:",
                            value=st.session_state.refined_text,
                            height=400,
                            label_visibility="collapsed"
                        )
                st.markdown("---")

            for idx, err in enumerate(st.session_state.detected_mistakes, 1):
                st.markdown(f"{idx}. {err}")
    else:
        st.success("✅ AI Analysis: Content looks good!")
    
    st.markdown("---")

    # NEW: Custom Instructions with Templates
    st.markdown("### 🗣️ Custom Instructions for AI")
    st.caption("Guide the AI on how to generate questions.")
    
    # NEW: Preset Templates
    col_template, col_fav = st.columns([3, 1])
    with col_template:
        template_options = {
            "Custom (Write your own)": "",
            "Focus on Definitions": "Generate questions that test understanding of key terms and definitions. Include 'what is' and 'define' type questions.",
            "Application-Based": "Create questions that require applying concepts to real-world scenarios. Focus on problem-solving and practical applications.",
            "Dates & Events": "Emphasize historical dates, chronological order, and significant events. Include timeline-based questions.",
            "Conceptual Understanding": "Generate deep conceptual questions that test understanding of 'why' and 'how', not just memorization.",
            "Mixed Difficulty": "Create a balanced mix of easy recall questions, medium application questions, and hard analytical questions.",
            "Exam Style - Professional": "Generate questions in formal exam style with precise language and clear options.",
            "Quick Quiz Style": "Create short, punchy questions suitable for quick assessment and review."
        }
        
        selected_template = st.selectbox("📋 Instruction Templates", list(template_options.keys()))
        
    with col_fav:
        # NEW: Save to favorites
        if st.button("⭐ Save to Favorites", use_container_width=True, disabled=(selected_template == "Custom (Write your own)")):
            if selected_template not in st.session_state.custom_instruction_favorites:
                st.session_state.custom_instruction_favorites.append(selected_template)
                st.success("Saved!")
    
    # Set instruction based on template
    if selected_template != "Custom (Write your own)":
        default_instruction = template_options[selected_template]
    else:
        default_instruction = st.session_state.custom_instructions
    
    st.session_state.custom_instructions = st.text_area(
        "Custom Instructions:",
        value=default_instruction,
        placeholder="e.g. Focus on scientific terms, avoid dates, include real-world applications...",
        height=120,
        label_visibility="collapsed"
    )
    
    # NEW: Show favorites
    if st.session_state.custom_instruction_favorites:
        st.caption("⭐ Your Favorites:")
        fav_cols = st.columns(len(st.session_state.custom_instruction_favorites))
        for idx, fav in enumerate(st.session_state.custom_instruction_favorites):
            with fav_cols[idx]:
                if st.button(f"📌 {fav[:20]}...", key=f"fav_{idx}", use_container_width=True):
                    st.session_state.custom_instructions = template_options[fav]
                    st.rerun()
    
    st.markdown("---")
    
    # Configuration options (keeping all original)
    col1, col2 = st.columns(2)
    with col1:
        auto_mode = st.checkbox("🤖 Auto Mode (AI decides structure)", value=True)
    with col2:
        difficulty = st.selectbox("🎯 Difficulty Level", options=['easy', 'medium', 'hard', 'mixed'], index=1)
    
    st.session_state.difficulty = difficulty
    
    col3, col4 = st.columns(2)
    with col3:
        test_duration = st.number_input("⏱️ Test Duration (minutes)", min_value=5, max_value=180, value=30, step=5)
    with col4:
        total_marks = st.number_input("📊 Total Marks (approximate)", min_value=10, max_value=200, value=50, step=10)
    
    # Manual configuration (unchanged)
    config = {
        'mcq': {'count': 5, 'marks': 2},
        'short': {'count': 5, 'marks': 3},
        'long': {'count': 3, 'marks': 5}
    }
    
    if not auto_mode:
        st.markdown("### 📝 Manual Configuration")
        col_mcq, col_short, col_long = st.columns(3)
        with col_mcq:
            st.info("**📝 Multiple Choice**")
            config['mcq']['count'] = st.number_input("Count", 0, 30, 5, key="mcq_c")
            config['mcq']['marks'] = st.number_input("Marks each", 1, 10, 2, key="mcq_m")
        with col_short:
            st.info("**✍️ Short Answer**")
            config['short']['count'] = st.number_input("Count", 0, 30, 5, key="short_c")
            config['short']['marks'] = st.number_input("Marks each", 1, 10, 3, key="short_m")
        with col_long:
            st.info("**📄 Long Answer**")
            config['long']['count'] = st.number_input("Count", 0, 20, 3, key="long_c")
            config['long']['marks'] = st.number_input("Marks each", 1, 20, 5, key="long_m")
    
    with st.expander("🔧 Advanced Options"):
        enable_partial = st.checkbox("Enable Partial Marks", value=True)
        avoid_duplicates = st.checkbox("Avoid duplicate questions", value=True)
        include_explanations = st.checkbox("Include answer explanations", value=True)
    
    st.session_state.config = {
        'auto_mode': auto_mode, 'difficulty': difficulty, 'duration': test_duration,
        'total_marks': total_marks, 'config': config, 'enable_partial': enable_partial,
        'avoid_duplicates': avoid_duplicates, 'include_explanations': include_explanations
    }
    
    st.markdown("---")
    
    col_back, col_gen = st.columns([1, 2])
    with col_back:
        if st.button("⬅️ Back (Edit Content)", use_container_width=True):
            st.session_state.show_viewer = True
            st.session_state.step = 'upload'
            st.rerun()
    
    with col_gen:
        if st.button("✨ Generate Test", type="primary", use_container_width=True):
            # NEW: Live preview container
            preview_container = st.empty()
            st.session_state.question_generation_progress = []
            
            with st.spinner("🧠 AI is creating your test..."):
                
                difficulty_instruction = {
                    'easy': "Beginner level",
                    'medium': "Intermediate level",
                    'hard': "Advanced level",
                    'mixed': "Mix of levels"
                }

                custom_prompt_text = ""
                if st.session_state.custom_instructions:
                    custom_prompt_text = f"\nUSER CUSTOM INSTRUCTIONS (IMPORTANT): {st.session_state.custom_instructions}\n"
                
                prompt = f"""
You are an expert test creator. Generate a high-quality test.

{custom_prompt_text}

VERIFIED CONTENT:
{st.session_state.refined_text[:20000]}

REQUIREMENTS:
- {config['mcq']['count']} Multiple Choice ({config['mcq']['marks']} marks each)
- {config['short']['count']} Short Answer ({config['short']['marks']} marks each)
- {config['long']['count']} Long Answer ({config['long']['marks']} marks each)
- Difficulty: {difficulty_instruction[difficulty]}
- Avoid duplicates
- Include explanations

Return valid JSON array:
[
  {{
    "type": "mcq",
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "correctAnswer": "B",
    "marks": {config['mcq']['marks']},
    "difficulty": "easy/medium/hard",
    "explanation": "..."
  }},
  {{
    "type": "short",
    "question": "...",
    "marks": {config['short']['marks']},
    "difficulty": "medium",
    "sampleAnswer": "...",
    "keyPoints": ["point1", "point2"]
  }}
]
"""
                questions = generate_with_smart_retry(prompt, expect_json=True)
                
                # NEW: Show live preview as questions are generated
                if questions and len(questions) > 0:
                    for idx, q in enumerate(questions):
                        st.session_state.question_generation_progress.append(q)
                        with preview_container.container():
                            st.markdown(f'<div class="gen-preview">✅ Generated Q{idx+1}: {q["question"][:60]}...</div>', unsafe_allow_html=True)
                            time.sleep(0.2)
                    
                    st.session_state.questions = questions
                    st.session_state.test_duration = test_duration
                    st.session_state.answers = {}
                    st.session_state.flagged = set()
                    st.session_state.current_q_index = 0
                    st.session_state.question_time_spent = {}
                    st.session_state.step = 'preview'
                    st.success(f"✅ Generated {len(questions)} questions successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Failed to generate test. Try again.")

# =============================================================================
# 11. STEP 2.5: PREVIEW (UNCHANGED - keeping all original features)
# =============================================================================
elif st.session_state.step == 'preview':
    st.markdown("## 👁️ Test Preview")
    st.caption("Review your test before starting the timer")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Questions", len(st.session_state.questions))
    with col2:
        st.metric("Total Marks", sum(q['marks'] for q in st.session_state.questions))
    with col3:
        st.metric("Duration", f"{st.session_state.test_duration} min")
    
    st.markdown("---")
    
    # Question breakdown
    st.markdown("### 📊 Question Breakdown")
    breakdown = {'mcq': 0, 'short': 0, 'long': 0}
    for q in st.session_state.questions:
        breakdown[q['type']] = breakdown.get(q['type'], 0) + 1
    
    col1, col2, col3 = st.columns(3)
    with col1: st.info(f"**📝 MCQ:** {breakdown.get('mcq', 0)}")
    with col2: st.info(f"**✍️ Short:** {breakdown.get('short', 0)}")
    with col3: st.info(f"**📄 Long:** {breakdown.get('long', 0)}")
    
    st.markdown("### 📋 All Questions")
    for i, q in enumerate(st.session_state.questions):
        with st.expander(f"Q{i+1}: {q['question'][:80]}... ({q['marks']} marks)"):
            st.markdown(f"**Type:** {q['type'].upper()} | **Difficulty:** {q.get('difficulty', 'N/A')}")
            st.markdown(f"**Question:** {q['question']}")
            if q['type'] == 'mcq':
                st.markdown("**Options:**")
                for opt in q['options']:
                    st.markdown(f"- {opt}")
    
    st.markdown("---")
    
    st.markdown("### 📥 Download Test Papers")
    col1, col2 = st.columns(2)
    with col1:
        question_paper = export_question_paper()
        st.download_button(label="📄 Download Question Paper", data=question_paper, file_name=f"test_paper_{datetime.now().strftime('%Y%m%d_%H%M')}.txt", mime="text/plain", use_container_width=True)
    with col2:
        answer_key = export_answer_key()
        st.download_button(label="🔑 Download Answer Key", data=answer_key, file_name=f"answer_key_{datetime.now().strftime('%Y%m%d_%H%M')}.txt", mime="text/plain", use_container_width=True)
    
    st.markdown("---")
    
    col_back, col_start = st.columns([1, 2])
    with col_back:
        if st.button("⬅️ Back to Configure", use_container_width=True):
            st.session_state.step = 'customize'
            st.rerun()
    with col_start:
        if st.button("🚀 Start Test (Timer Begins!)", type="primary", use_container_width=True):
            st.session_state.test_start_time = time.time()
            st.session_state.test_paused = False
            st.session_state.total_pause_duration = 0
            # Initialize time tracking for each question
            for i in range(len(st.session_state.questions)):
                st.session_state.question_time_spent[i] = 0
            st.session_state.step = 'test'
            st.rerun()

# =============================================================================
# 12. STEP 3: TAKE TEST (ENHANCED WITH PAUSE/KEYBOARD)
# =============================================================================
elif st.session_state.step == 'test':
    
    # Add keyboard shortcuts
    add_keyboard_shortcuts()
    
    # Timer logic with pause support
    remaining = get_remaining_time()
    if remaining <= 0 and not st.session_state.test_paused:
        st.session_state.step = 'evaluate'
        st.rerun()
    
    # Auto-refresh removed to prevent losing focus while typing
    pass
    
    # Header with timer
    col_title, col_timer, col_pause = st.columns([2, 1, 1])
    with col_title:
        st.markdown(f"## Question {st.session_state.current_q_index + 1} of {len(st.session_state.questions)}")
    with col_timer:
        warning = check_time_warnings(remaining)
        if st.session_state.test_paused:
            timer_class = "timer-paused"
            timer_text = f"⏸️ PAUSED<br>{format_time(remaining)}"
        elif remaining <= 60:
            timer_class = "timer-danger"
            timer_text = f"⏱️ {format_time(remaining)}"
        elif remaining <= 300:
            timer_class = "timer-warning"
            timer_text = f"⏱️ {format_time(remaining)}"
        else:
            timer_class = "timer-box"
            timer_text = f"⏱️ {format_time(remaining)}"
        
        st.markdown(f'<div class="{timer_class}">{timer_text}</div>', unsafe_allow_html=True)
        if warning and not st.session_state.test_paused: 
            st.warning(warning)
    
    with col_pause:
        # NEW: Pause/Resume button
        pause_label = "▶️ Resume" if st.session_state.test_paused else "⏸️ Pause"
        if st.button(pause_label, use_container_width=True, key="pause_btn"):
            toggle_pause()
            st.rerun()
    
    st.markdown("---")
    
    # Keyboard shortcuts info
    st.caption("⌨️ Shortcuts: ← Previous | → Next | F Flag | S Submit")
    
    # Navigation grid
    st.markdown("### 🗺️ Quick Navigation")
    nav_html = '<div class="progress-grid">'
    for i in range(len(st.session_state.questions)):
        classes = []
        if i == st.session_state.current_q_index: classes.append('current')
        elif i in st.session_state.flagged: classes.append('flagged')
        elif i in st.session_state.answers: classes.append('answered')
        else: classes.append('unanswered')
        nav_html += f'<div class="progress-item {" ".join(classes)}">{i+1}</div>'
    nav_html += '</div>'
    st.markdown(nav_html, unsafe_allow_html=True)
    
    leg_col1, leg_col2, leg_col3, leg_col4 = st.columns(4)
    with leg_col1: st.markdown("🟦 **Current**")
    with leg_col2: st.markdown("🟩 **Answered**")
    with leg_col3: st.markdown("🟨 **Flagged**")
    with leg_col4: st.markdown("🟥 **Unanswered**")
    
    st.markdown("---")
    
    # Current question
    idx = st.session_state.current_q_index
    q = st.session_state.questions[idx]
    
    st.markdown(f"""<div class="question-card"><h3>{q['question']}</h3></div>""", unsafe_allow_html=True)
    
    col_type, col_marks, col_flag = st.columns([1, 1, 2])
    with col_type: st.caption(f"**Type:** {q['type'].upper()}")
    with col_marks: st.caption(f"**Marks:** {q['marks']}")
    with col_flag:
        is_flagged = idx in st.session_state.flagged
        flag_label = "❌ Remove Flag" if is_flagged else "🚩 Flag for Review"
        # Corrected: Removed the invalid 'data-testid' argument
        if st.button(flag_label, use_container_width=True, key=f"flag_{idx}"):
            if is_flagged: 
                st.session_state.flagged.remove(idx)
            else: 
                st.session_state.flagged.add(idx)
            st.rerun()
    
    st.divider()
    
    # Answer input
    st.markdown("### Your Answer:")
    answer_key = f"ans_{idx}"
    current_answer = st.session_state.answers.get(idx, "")
    
    if q['type'] == 'mcq':
        default_index = q['options'].index(current_answer) if current_answer in q['options'] else None
        user_choice = st.radio("Select one option:", q['options'], index=default_index, key=answer_key, label_visibility="collapsed")
        if user_choice: st.session_state.answers[idx] = user_choice
    else:
        height = 200 if q['type'] == 'long' else 150
        # NEW: Show word count for text answers
        word_count = len(current_answer.split()) if current_answer else 0
        st.caption(f"📝 Words: {word_count}")
        
        user_answer = st.text_area("Write your answer here:", value=current_answer, height=height, key=answer_key, label_visibility="collapsed", placeholder="Type your answer here...")
        if user_answer != current_answer: st.session_state.answers[idx] = user_answer
    
    st.markdown("💡 *Answer is saved automatically*")
    st.divider()
    
    # Navigation
    col_prev, col_summary, col_next = st.columns([1, 1, 1])
    with col_prev:
        if st.button("⬅️ Previous", disabled=(idx == 0), use_container_width=True):
            st.session_state.current_q_index -= 1
            st.rerun()
    with col_summary:
        st.caption(f"📊 {len(st.session_state.answers)}/{len(st.session_state.questions)} answered")
        st.caption(f"🚩 {len(st.session_state.flagged)} flagged")
    with col_next:
        if idx < len(st.session_state.questions) - 1:
            if st.button("Next ➡️", use_container_width=True):
                st.session_state.current_q_index += 1
                st.rerun()
        else:
            if st.button("👁️ Review All", type="secondary", use_container_width=True):
                st.session_state.step = 'review'
                st.rerun()
    
    st.markdown("---")
    
    # Submit button
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        if st.button("✅ Submit Test Now", type="primary", use_container_width=True):
            if len(st.session_state.answers) < len(st.session_state.questions):
                unanswered = len(st.session_state.questions) - len(st.session_state.answers)
                st.warning(f"⚠️ You have {unanswered} unanswered questions.")
                if st.button("⚠️ Yes, Submit Anyway"):
                    st.session_state.step = 'evaluate'
                    st.rerun()
            else:
                st.session_state.step = 'evaluate'
                st.rerun()

# =============================================================================
# 13. STEP 3.5: REVIEW SCREEN (UNCHANGED - keeping all original)
# =============================================================================
elif st.session_state.step == 'review':
    st.markdown("## 👁️‍🗨️ Final Review")
    st.caption("Review all questions and answers before final submission")
    
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total", len(st.session_state.questions))
    answered_count = len([i for i in st.session_state.answers if st.session_state.answers[i]])
    with col2: st.metric("Answered", answered_count)
    with col3: st.metric("Flagged", len(st.session_state.flagged))
    with col4: st.metric("Unanswered", len(st.session_state.questions) - answered_count)
    
    st.markdown("---")
    
    for i, q in enumerate(st.session_state.questions):
        with st.expander(f"Question {i+1}: {q['question'][:100]}...", expanded=False):
            col_status, col_actions = st.columns([2, 1])
            with col_status:
                status = []
                if i in st.session_state.answers and st.session_state.answers[i]:
                    status.append("✅ Answered")
                else:
                    status.append("❌ Not answered")
                if i in st.session_state.flagged:
                    status.append("🚩 Flagged")
                st.caption(" | ".join(status))
            with col_actions:
                if st.button("Go to", key=f"goto_{i}", use_container_width=True):
                    st.session_state.current_q_index = i
                    st.session_state.step = 'test'
                    st.rerun()
            st.markdown(f"**Question:** {q['question']}")
            st.markdown(f"**Type:** {q['type'].upper()} | **Marks:** {q['marks']}")
            answer = st.session_state.answers.get(i, "")
            st.markdown(f"**Your Answer:**")
            if answer: st.info(answer)
            else: st.error("No answer provided")
    
    st.markdown("---")
    
    col_back, col_submit = st.columns([1, 2])
    with col_back:
        if st.button("⬅️ Back to Test", use_container_width=True):
            st.session_state.step = 'test'
            st.rerun()
    with col_submit:
        if st.button("🚀 Final Submission & AI Grading", type="primary", use_container_width=True):
            st.session_state.step = 'evaluate'
            st.rerun()

# =============================================================================
# 14. STEP 4: AI EVALUATION (ENHANCED WITH ANSWER HIGHLIGHTING)
# =============================================================================
elif st.session_state.step == 'evaluate':
    st.markdown("## 🤖 AI Grading in Progress")
    st.caption("Evaluating your answers with advanced AI...")
    
    st.markdown("---")
    
    if not st.session_state.results:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        evals = []
        total_score = 0
        max_score = sum(q['marks'] for q in st.session_state.questions)
        question_feedback = []
        
        for i, q in enumerate(st.session_state.questions):
            # Calculate time spent (default to 0 if not tracked per question)
            time_taken = st.session_state.question_time_spent.get(i, 0)
            
            status_text.text(f"📝 Grading Question {i+1}/{len(st.session_state.questions)} - Analyzing...")
            
            answer = st.session_state.answers.get(i, "")
            is_answered = bool(answer and answer.strip())
            
            question_data = {
                'question': q['question'],
                'type': q['type'],
                'marks': q['marks'],
                'user_answer': answer,
                'question_num': i + 1,
                'is_answered': is_answered,
                'time_spent': time_taken
            }
            
            # --- MCQ GRADING ---
            # --- MCQ GRADING (UPDATED & FIXED) ---
            if q['type'] == 'mcq':
                # FIX: More robust MCQ matching
                correct_option_char = q.get('correctAnswer', '').strip().split('.')[0].strip().lower()
                user_ans_clean = answer.strip().split('.')[0].split(')')[0].strip().lower()
                
                is_correct = (user_ans_clean == correct_option_char)

                score = q['marks'] if is_correct else 0
                
                # For MCQs, highlighting is simple status
                highlighted_html = f"<span class='answer-correct'>{answer}</span>" if is_correct else f"<span class='answer-incorrect'>{answer}</span>"
                
                question_data.update({
                    'score': score,
                    'is_correct': is_correct,
                    'correct_answer': q.get('correctAnswer', ''), # Show original format to user
                    'feedback': "Correct! 🎉" if is_correct else f"Incorrect. The correct option was {q.get('correctAnswer', '')}.",
                    'explanation': q.get('explanation', ''),
                    'highlighted_answer': highlighted_html,
                    'strengths': [],
                    'improvements': []
                })
            
            # --- SUBJECTIVE GRADING (SHORT/LONG) ---
            else:
                # Construct prompt for AI Grading with Highlighting Request
                correction_mode = st.session_state.correction_level
                
                prompt = f"""
                Act as a strict teacher. Grade this student answer.
                
                QUESTION: {q['question']}
                MAX MARKS: {q['marks']}
                STUDENT ANSWER: "{answer}"
                REFERENCE CONTENT: {st.session_state.refined_text[:1000]}...
                
                GRADING TASKS:
                1. Assign a score based on accuracy and completeness.
                2. Provide constructive feedback.
                3. Create a 'highlighted_answer' version of the student's text:
                   - Wrap correct factual parts in <span class='answer-correct'>...</span>
                   - Wrap incorrect/false parts in <span class='answer-incorrect'>...</span>
                   - Wrap partial/vague parts in <span class='answer-partial'>...</span>
                   - Leave neutral text as is.
                
                Return ONLY JSON:
                {{
                    "score": float,
                    "feedback": "string",
                    "highlighted_answer": "html_string",
                    "strengths": ["list"],
                    "improvements": ["list"],
                    "percentage": float
                }}
                """
                
                try:
                    # Use smart retry to ensure valid JSON
                    grading_result = generate_with_smart_retry(prompt, expect_json=True)
                    
                    if grading_result:
                        score = min(q['marks'], grading_result.get('score', 0))
                        
                        question_data.update({
                            'score': score,
                            'is_correct': grading_result.get('percentage', 0) >= 50,
                            'correct_answer': q.get('sampleAnswer', 'Refer to feedback.'),
                            'feedback': grading_result.get('feedback', 'No feedback provided.'),
                            'highlighted_answer': grading_result.get('highlighted_answer', answer),
                            'strengths': grading_result.get('strengths', []),
                            'improvements': grading_result.get('improvements', []),
                            'percentage': grading_result.get('percentage', 0)
                        })
                    else:
                        # Fallback if AI fails
                        question_data.update({
                            'score': 0, 
                            'is_correct': False, 
                            'feedback': 'AI Grading unavailable.',
                            'highlighted_answer': answer,
                            'correct_answer': 'N/A'
                        })
                        
                except Exception as e:
                    question_data.update({
                        'score': 0, 
                        'is_correct': False, 
                        'feedback': f'Error during grading: {str(e)}',
                        'highlighted_answer': answer
                    })
            
            total_score += question_data['score']
            evals.append(question_data)
            question_feedback.append(f"Q{i+1}: {question_data['score']}/{q['marks']}")
            progress_bar.progress((i + 1) / len(st.session_state.questions))
        
        # Finalize Results
        percentage_score = (total_score / max_score * 100) if max_score > 0 else 0
        
        st.session_state.results = {
            'evals': evals,
            'total_score': total_score,
            'max_score': max_score,
            'percentage': percentage_score,
            'question_feedback': question_feedback,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add to History
        st.session_state.test_history.append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'score': f"{total_score}/{max_score}",
            'percentage': f"{percentage_score:.1f}%",
            'questions': len(evals),
            'details': st.session_state.results
        })
        
        st.rerun()

    # --- DISPLAY RESULTS DASHBOARD ---
    results = st.session_state.results
    if results:
        percentage = results['percentage']
        
        # 1. Performance Header
        st.markdown(f"""
        <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin-bottom: 20px;">
            <h1>🏆 Test Result</h1>
            <h2 style="font-size: 60px; margin: 10px 0;">{percentage:.1f}%</h2>
            <p style="font-size: 24px;">Score: {results['total_score']} / {results['max_score']}</p>
            <p style="font-size: 14px; opacity: 0.8;">{datetime.now().strftime('%B %d, %Y • %H:%M')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 2. Key Metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            if percentage >= 90: st.success("🌟 Excellent")
            elif percentage >= 70: st.info("👍 Good")
            elif percentage >= 50: st.warning("📉 Average")
            else: st.error("🛑 Needs Work")
        with m2: st.metric("Questions", len(results['evals']))
        with m3: st.metric("Duration", f"{st.session_state.test_duration}m")
        with m4: st.metric("Avg Time/Q", "N/A" if st.session_state.test_paused else "~") # Placeholder for future expansion
        
        st.markdown("---")
        
        # 3. Detailed Question Breakdown
        st.markdown("### 🔍 Detailed Analysis")
        
        for eval_item in results['evals']:
            i = eval_item['question_num']
            q_score = eval_item['score']
            q_max = eval_item['marks']
            
            # Determine color based on score
            if q_score == q_max: border_color = "#28a745" # Green
            elif q_score > 0: border_color = "#ffc107" # Yellow
            else: border_color = "#dc3545" # Red
            
            with st.expander(f"Q{i}: {eval_item['question'][:60]}... ({q_score}/{q_max} Marks)"):
                col_review_L, col_review_R = st.columns([3, 1])
                
                with col_review_L:
                    st.markdown(f"**Question:** {eval_item['question']}")
                    
                    st.markdown("**Your Answer (Analyzed):**")
                    # Display the HTML Highlighted Answer
                    if eval_item.get('highlighted_answer'):
                        st.markdown(f"<div>{eval_item['highlighted_answer']}</div>", unsafe_allow_html=True)
                    else:
                        st.info(eval_item['user_answer'])
                    
                    st.markdown(f"**Feedback:** {eval_item.get('feedback', '')}")
                    
                    if eval_item.get('strengths'):
                        st.markdown("**✅ Strengths:** " + ", ".join(eval_item['strengths']))
                    if eval_item.get('improvements'):
                        st.markdown("**💡 Improvements:** " + ", ".join(eval_item['improvements']))
                
                with col_review_R:
                    # Visual Score Bar
                    score_pct = (q_score / q_max) * 100
                    st.markdown(f"""
                    <div style="text-align: center; border: 2px solid {border_color}; border-radius: 10px; padding: 10px; background: {border_color}10;">
                        <h3 style="color: {border_color}; margin:0;">{q_score}/{q_max}</h3>
                        <div style="background: #eee; height: 8px; border-radius: 4px; margin-top: 5px;">
                            <div style="background: {border_color}; width: {score_pct}%; height: 100%; border-radius: 4px;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if 'explanation' in eval_item and eval_item['explanation']:
                        with st.popover("ℹ️ Explanation"):
                            st.info(eval_item['explanation'])
                            
                    if eval_item['type'] == 'MCQ':
                        st.caption(f"Correct: {eval_item['correct_answer']}")

        st.markdown("---")
        
        # 4. Export & Navigation
        st.markdown("### 📤 Export Results")
        c_csv, c_report, c_qa = st.columns(3)
        
        with c_csv:
            csv = export_to_csv(results)
            st.download_button("📊 Download CSV Data", csv, "results.csv", "text/csv", use_container_width=True)
            
        with c_report:
            # Generate Text Report
            report_txt = f"TEST REPORT - {datetime.now()}\nScore: {percentage:.1f}%\n\n"
            for e in results['evals']:
                report_txt += f"Q{e['question_num']}: {e['question']}\nAns: {e['user_answer']}\nFeedback: {e['feedback']}\n\n"
            st.download_button("📄 Download Full Report", report_txt, "report.txt", "text/plain", use_container_width=True)
            
        with c_qa:
            qa_txt = export_question_paper() + "\n\n" + export_answer_key()
            st.download_button("📚 Download Q&A Key", qa_txt, "study_key.txt", "text/plain", use_container_width=True)
            
        st.markdown("---")
        
        # 5. Bottom Actions
        col_new, col_hist, col_home = st.columns(3)
        with col_new:
            if st.button("🔄 Retake / New Test", use_container_width=True):
                # Keep history, clear current test data
                hist = st.session_state.test_history
                reset_application()
                st.session_state.test_history = hist
                st.session_state.step = 'customize' # Go back to config
                st.rerun()
                
        with col_hist:
            if st.button("📜 View History", use_container_width=True):
                if st.session_state.test_history:
                    df_hist = pd.DataFrame(st.session_state.test_history)
                    st.dataframe(df_hist[['date', 'score', 'percentage', 'questions']])
                else:
                    st.info("No history yet.")
                    
        with col_home:
            if st.button("🏠 Home (Reset All)", use_container_width=True):
                reset_application()
                st.session_state.step = 'upload'
                st.rerun()