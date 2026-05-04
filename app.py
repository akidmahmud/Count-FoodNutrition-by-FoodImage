import streamlit as st
import requests
from PIL import Image
import io
import datetime
import sqlite3
import base64
import os
import google.generativeai as genai
import json
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime

# Load environment variables
load_dotenv()

def parse_nutrition_response(response_text):
    """
    Parse the JSON response from OpenAI
    """
    try:
        
        # Clean up the response: remove markdown code block indicators and extra whitespace
        cleaned_response = response_text.replace("```json", "").replace("```", "").strip()
        
        # Parse JSON response
        data = json.loads(cleaned_response)
        
        # Extract all available macronutrients
        macros = data['macronutrients']
        # Add any additional macronutrients if they exist
        additional_macros = ['calories', 'sugar', 'saturated_fat', 'cholesterol', 'sodium']
        for macro in additional_macros:
            if macro in macros:
                macros[macro] = macros[macro]
        
        # Extract all available micronutrients
        micros = data['micronutrients']
        # Add any additional micronutrients if they exist
        additional_micros = [
            'vitamin_d', 'vitamin_e', 'vitamin_k', 'thiamin', 'riboflavin', 
            'niacin', 'vitamin_b6', 'folate', 'vitamin_b12', 'pantothenic_acid', 
            'potassium', 'magnesium', 'zinc', 'selenium', 'copper', 'manganese'
        ]
        for micro in additional_micros:
            if micro in micros:
                micros[micro] = micros[micro]
        
        # Extract any additional nutritional information if available
        additional_info = {}
        possible_fields = ['serving_size', 'total_weight', 'dietary_restrictions', 'allergens']
        for field in possible_fields:
            if field in data:
                additional_info[field] = data[field]
        
        return {
            'food_items': data['identified_foods'],
            'macronutrients': macros,
            'micronutrients': micros,
            'improvements': data['improvements'],
            'additional_info': additional_info
        }
    except Exception as e:
        st.error(f"Error parsing nutrition data: {str(e)}")
        st.write(f"Exception details: {str(e)}")
        return {
            'food_items': [],
            'macronutrients': {
                'carbohydrates': 0, 
                'protein': 0, 
                'fat': 0,
                'calories': 0,
                'sugar': 0,
                'saturated_fat': 0,
                'cholesterol': 0,
                'sodium': 0
            },
            'micronutrients': {
                'vitamin_a': 0,
                'vitamin_c': 0,
                'calcium': 0,
                'iron': 0,
                'fiber': 0
            },
            'improvements': {'suggestions': [], 'context': ''},
            'additional_info': {}
        }


def init_db():
    """
    Initialize database if it doesn't exist.
    Only creates table if it doesn't already exist.
    """
    try:
        conn = sqlite3.connect("nutrition_data.db")
        cursor = conn.cursor()
        
        # Create table only if it doesn't exist
        cursor.execute('''CREATE TABLE IF NOT EXISTS records (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
            image BLOB,
            timestamp TEXT,
            macronutrients TEXT,
            micronutrients TEXT,
            food_items TEXT,
            improvements TEXT,
            goal TEXT
        )''')
        
        conn.commit()
        conn.close()
        st.write("Database initialized successfully!")
        
    except Exception as e:
        st.error(f"Error initializing database: {str(e)}")

def save_record(image, macronutrients, micronutrients, food_items, improvements, goal, is_refinement, custom_timestamp=None):
    try:
        conn = sqlite3.connect("nutrition_data.db")
        cursor = conn.cursor()
        
        # Convert data to JSON strings for storage
        macronutrients_json = json.dumps(macronutrients)
        micronutrients_json = json.dumps(micronutrients)
        food_items_json = json.dumps(food_items)
        improvements_json = json.dumps(improvements)
        
        # Use custom timestamp if provided, otherwise use current time
        timestamp = custom_timestamp.strftime('%Y-%m-%d %H:%M:%S') if custom_timestamp else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if is_refinement:
            # Update the most recent record instead of creating a new one
            cursor.execute("""
                UPDATE records 
                SET macronutrients = ?,
                    micronutrients = ?,
                    food_items = ?,
                    improvements = ?
                WHERE id = (
                    SELECT id 
                    FROM records 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                )
            """, (
                macronutrients_json,
                micronutrients_json,
                food_items_json,
                improvements_json
            ))
        else:
            # Insert a new record
            cursor.execute("""
                INSERT INTO records (image, timestamp, macronutrients, micronutrients, food_items, improvements, goal) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                image, 
                timestamp,
                macronutrients_json,
                micronutrients_json,
                food_items_json,
                improvements_json,
                goal
            ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error saving to database: {str(e)}")

# Load environment variables
load_dotenv()

# Initialize Gemini API key (supports both local .env and Streamlit Cloud secrets)
api_key = (
    os.getenv('GEMINI_API_KEY') or
    os.getenv('OPENAI_API_KEY') or
    st.secrets.get('GEMINI_API_KEY') or
    st.secrets.get('OPENAI_API_KEY')
)
if not api_key:
    st.error("API key is not set. Please check your .env file or Streamlit secrets.")
    st.stop()
    
# Set the API key directly
genai.configure(api_key=api_key)

# Function to analyze image with OpenAI
def analyze_image_with_image_recognition(image_bytes):
    prompt_text = """Analyze the food items in this image and provide the nutritional information in the following JSON format only:
{
    "identified_foods": [
        "food item 1",
        "food item 2",
        ...
    ],
    "macronutrients": {
        "carbohydrates": number,
        "protein": number,
        "fat": number,
        "calories": number,
        "sugar": number
    },
    "micronutrients": {
        "vitamin_a": number,
        "vitamin_c": number,
        "calcium": number,
        "iron": number,
        "fiber": number
    },
    "improvements": {
        "suggestions": [
            "🌟 Great choice on including [positive aspect]!",
            "💪 Keep up the good work with [healthy element]!",
            "💡 Consider adding [suggestion] to boost nutrition"
        ],
        "context": "Start with encouraging feedback about the healthy aspects of the meal, then provide constructive suggestions. Use emojis like 🥗 for healthy choices, 💪 for protein-rich foods, 🌟 for balanced meals, 🍎 for fruits/vegetables, 💚 for nutritious choices."
    }
}
Consider the user's goal when suggesting improvements. Be encouraging when healthy choices are present. Provide only the JSON response without any additional text or explanation."""

    img = Image.open(io.BytesIO(image_bytes))
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content([prompt_text, img])
    return response


# to reduce the size of the image to avoid the error of the image being too large
def process_image_for_analysis(image, max_size=(800, 800), quality=85):
    """
    Processes image by resizing and compressing while maintaining quality.
    Args:
        image: PIL Image object
        max_size: tuple of maximum dimensions (width, height)
        quality: JPEG compression quality (0-100)
    Returns:
        bytes of the processed image
    """
    try:
        # Create a copy to avoid modifying original
        img_copy = image.copy()
        
        # Resize using LANCZOS resampling
        img_copy.thumbnail(max_size, Image.LANCZOS)
        
        # Compress and convert to bytes
        image_bytes = io.BytesIO()
        img_copy.save(image_bytes, format='JPEG', quality=quality)
        
        return image_bytes.getvalue()
    except Exception as e:
        st.error(f"Error processing image: {str(e)}")
        return None

# # Initialize database
init_db()

# # Streamlit UI
st.title("Macronutrient Counter")
st.sidebar.header("Your Goal")
goal = st.sidebar.radio(
    "Select your goal:",
    [
        "Maintain weight",
        "Fat loss",
        "Weight gain",
        "Muscle Gain",
        "Pregnancy",
        "Body Building Competition",
        "Marathon Training",
        "Endurance Training",
        "Senior Citizen",
        "Diabetic Patient",
        "Kidney Patient"
    ],
    help="Select your primary health or fitness goal. This will help tailor the nutritional analysis and recommendations to your specific needs."
)
st.header("Upload Food Image")
uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])



# Initialize session state for meal time and date if not already set
if 'meal_time' not in st.session_state:
    st.session_state.meal_time = datetime.now().time()
if 'meal_date' not in st.session_state:
    st.session_state.meal_date = datetime.now().date()

# Add time input with default to current time
col1, col2 = st.columns([2, 1])
with col1:
    selected_time = st.time_input(
        "Select meal time (optional)",
        value=st.session_state.meal_time,
        help="Select the time when this meal was consumed. Defaults to current time if not specified.",
        key='time_input'
    )
    # Update session state when time changes
    if selected_time != st.session_state.meal_time:
        st.session_state.meal_time = selected_time

with col2:
    selected_date = st.date_input(
        "Select date (optional)",
        value=st.session_state.meal_date,
        help="Select the date when this meal was consumed. Defaults to today if not specified.",
        key='date_input'
    )
    # Update session state when date changes
    if selected_date != st.session_state.meal_date:
        st.session_state.meal_date = selected_date

# Combine date and time for timestamp
custom_timestamp = datetime.combine(selected_date, selected_time)

# Update the main UI section where results are displayed
if uploaded_file:
    # Clear session state when a new image is uploaded
    if 'last_uploaded_file' not in st.session_state or st.session_state.last_uploaded_file != uploaded_file.name:
        st.session_state.analysis_done = False
        st.session_state.initial_result = None
        st.session_state.image_bytes = None
        st.session_state.base64_image = None
        st.session_state.last_uploaded_file = uploaded_file.name
        if 'record_saved' in st.session_state:
            del st.session_state.record_saved
        # Force a rerun to clear displayed results
        st.rerun()
    
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image", width=700)

    # First Analysis Button
    if not st.session_state.analysis_done and st.button("Analyze Image"):
        with st.spinner("🔄 Analyzing your food image... This may take a few seconds."):
            try:
                # Ensure image exists and is valid
                if image is None:
                    st.error("Please upload an image first")
                    st.stop()
                
                # Process image
                image_bytes = process_image_for_analysis(image)
                if image_bytes is None:
                    st.error("Failed to process image")
                    st.stop()
                    
                st.session_state.image_bytes = image_bytes
                st.session_state.base64_image = base64.b64encode(image_bytes).decode("utf-8")
                
                # Initial analysis
                result = analyze_image_with_image_recognition(image_bytes)
                message_content = result.text
                parsed_result = parse_nutrition_response(message_content)
                
                # Save to session state
                st.session_state.initial_result = parsed_result
                st.session_state.analysis_done = True
                
                # Save to database only if not already saved
                if 'record_saved' not in st.session_state:
                    save_record(
                        image_bytes,
                        parsed_result['macronutrients'],
                        parsed_result['micronutrients'],
                        parsed_result['food_items'],
                        parsed_result['improvements'],
                        goal,
                        is_refinement=False,
                        custom_timestamp=custom_timestamp
                    )
                    st.session_state.record_saved = True
                
                st.success("✅ Analysis completed successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")
    # Show results and refinement options after initial analysis
    if st.session_state.analysis_done:
        parsed_result = st.session_state.initial_result
        
        # Add optional meal description input with its own submit button
        st.write("---")
        col1, col2 = st.columns([3, 1])
        with col1:
            meal_description = st.text_area(
                "Optional: Add a brief description of the meal to improve analysis accuracy",
                placeholder="Example: Home-cooked Indian thali with roti, dal, and mixed vegetables",
                help="This will help improve the accuracy of the nutritional analysis",
                key="meal_description"
            )
        with col2:
            refine_button = st.button("Refine Analysis", key="refine")
        
        # Handle refinement
        if refine_button and meal_description:
            with st.spinner("Refining analysis with your description..."):
                try:
                    # Convert the current analysis to a string for context
                    current_analysis = json.dumps(parsed_result, indent=2)
                    
                    prompt_text = f'''Analyze the food items in this image, considering the following user description: '{meal_description}'
Your previous analysis was:
{current_analysis}
Please provide a refined analysis based on the user's description and your previous analysis. 
Keep the values that seem accurate and adjust only what needs to be changed based on the new information.
Provide the nutritional information in the following JSON format only:
{{
    "identified_foods": [
        "food item 1",
        "food item 2"
    ],
    "macronutrients": {{
        "carbohydrates": number,
        "protein": number,
        "fat": number,
        "calories": number,
        "sugar": number
    }},
    "micronutrients": {{
        "vitamin_a": 0,
        "vitamin_c": 0,
        "calcium": 0,
        "iron": 0,
        "fiber": 0
    }},
    "improvements": {{
        "suggestions": [
            "🌟 Great choice on including [positive aspect]!",
            "💪 Keep up the good work with [healthy element]!",
            "💡 Consider adding [suggestion] to boost nutrition"
        ],
        "context": "Start with encouraging feedback about the healthy aspects of the meal, then provide constructive suggestions. Use emojis like 🥗 for healthy choices, 💪 for protein-rich foods, 🌟 for balanced meals, 🍎 for fruits/vegetables, 💚 for nutritious choices."
    }}
}}'''

                    # Update the analyze function to include meal description
                    img_bytes = base64.b64decode(st.session_state.base64_image)
                    img = Image.open(io.BytesIO(img_bytes))
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    response = model.generate_content([prompt_text, img])
                    # Update parsed result with refined analysis
                    parsed_result = parse_nutrition_response(response.text)
                    st.session_state.initial_result = parsed_result
                    st.success("Analysis refined successfully!")
                    
                   
                    
                    st.success("✅ Analysis refined and saved successfully!")
                    
                except Exception as e:
                    st.error(f"Error during refinement: {str(e)}")
                    st.write("Using original analysis results...")
        
        # Display results
        tab1, tab2, tab3 = st.tabs(["Macronutrients", "Micronutrients", "Suggestions"])
        
        with tab1:
            st.subheader("Macronutrients Analysis")
            st.write("Identified Foods:")
            for food in parsed_result['food_items']:
                st.write(f"- {food}")
                
            st.write("\nMacronutrients:")
            for macro, value in parsed_result['macronutrients'].items():
                # Format the display based on the nutrient type
                if macro == 'calories':
                    st.write(f"- {macro.title()}: {value} kcal")
                elif macro in ['sodium', 'cholesterol']:
                    st.write(f"- {macro.title()}: {value} mg")
                else:
                    st.write(f"- {macro.title()}: {value}g")
        
        with tab2:
            st.subheader("Micronutrients Analysis")
            for micro, value in parsed_result['micronutrients'].items():
                # Format the display based on the nutrient type
                if micro in ['vitamin_a']:
                    st.write(f"- {micro.replace('_', ' ').title()}: {value} IU")
                elif micro in ['fiber']:
                    st.write(f"- {micro.title()}: {value}g")
                else:
                    st.write(f"- {micro.replace('_', ' ').title()}: {value} mg")

            # Display additional information if available
            if parsed_result['additional_info']:
                st.write("\nAdditional Information:")
                for key, value in parsed_result['additional_info'].items():
                    st.write(f"- {key.replace('_', ' ').title()}: {value}")
        
        with tab3:
            st.subheader("Suggested Improvements")
            st.write("Based on your goal:", goal)
            for suggestion in parsed_result['improvements']['suggestions']:
                st.write(f"- {suggestion}")
            st.write("\nContext:")
            st.write(parsed_result['improvements']['context'])
            
            # Add Past Records Analysis section
            st.write("---")
            st.subheader("📊 Historical Diet Analysis")
            if st.button("Analyze My Diet History"):
                try:
                    conn = sqlite3.connect("nutrition_data.db")
                    cursor = conn.cursor()
                    cursor.execute("SELECT macronutrients, micronutrients, food_items, goal, timestamp FROM records ORDER BY timestamp DESC")
                    past_records = cursor.fetchall()
                    conn.close()

                    if not past_records:
                        st.info("No past records found. Add more meals to get a detailed analysis!")
                    else:
                        # Prepare data for analysis
                        analysis_prompt = {
                            "records": [],
                            "current_goal": goal,
                            "total_records": len(past_records)
                        }

                        for record in past_records:
                            analysis_prompt["records"].append({
                                "macronutrients": json.loads(record[0]),
                                "micronutrients": json.loads(record[1]),
                                "foods": json.loads(record[2]),
                                "goal": record[3],
                                "timestamp": record[4]
                            })

                        # Call Gemini for analysis
                        with st.spinner("🔄 Analyzing your diet history..."):
                            prompt_text = f"""Analyze the following diet history and provide a comprehensive nutritional analysis. 
                                        Diet History: {json.dumps(analysis_prompt, indent=2)}
                                        Please provide analysis in the following format:
                                        {{
                                            "trend_analysis": {{
                                                "macronutrient_trends": [
                                                    "🔍 Detailed observations about macronutrient patterns",
                                                    "⚠️ Any concerning patterns or excesses"
                                                ],
                                                "micronutrient_trends": [
                                                    "🔍 Key observations about vitamin and mineral intake",
                                                    "⚠️ Notable deficiencies or concerns"
                                                ]
                                            }},
                                            "goal_alignment": {{
                                                "progress": [
                                                    "✅ Areas aligned with {goal}",
                                                    "❌ Areas needing improvement"
                                                ],
                                                "recommendations": [
                                                    "💡 Specific actionable recommendations",
                                                    "🎯 Goal-specific suggestions"
                                                ]
                                            }},
                                            "dietary_balance": {{
                                                "strengths": [
                                                    "💪 Strong aspects of the diet",
                                                    "🌟 Particularly healthy choices"
                                                ],
                                                "improvements": [
                                                    "📈 Areas for improvement",
                                                    "🔄 Suggested dietary adjustments"
                                                ]
                                            }},
                                            "alerts": [
                                                "⚠️ Alert: [specific concern]",
                                                "📢 Warning: [potential issue]"
                                            ]
                                        }}"""
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            response = model.generate_content(prompt_text)

                            try:
                                analysis_text = response.text.replace("```json", "").replace("```", "").strip()
                                analysis = json.loads(analysis_text)
                                
                                # Create DataFrame from records for plotting
                                df_records = []
                                for record in analysis_prompt["records"]:
                                    timestamp = datetime.strptime(record["timestamp"], '%Y-%m-%d %H:%M:%S')
                                    macros = record["macronutrients"]
                                    df_records.append({
                                        'timestamp': timestamp,
                                        'calories': macros.get('calories', 0),
                                        'protein': macros.get('protein', 0),
                                        'carbohydrates': macros.get('carbohydrates', 0),
                                        'fat': macros.get('fat', 0)
                                    })
                                
                                df = pd.DataFrame(df_records)
                                
                                # Display Trend Analysis
                                st.write("### 📈 Nutritional Trends")
                                
                                # Remove the line charts and keep only the pie chart
                                # Macronutrient Distribution Pie Chart (Average)
                                avg_macros = {
                                    'Protein': df['protein'].mean(),
                                    'Carbohydrates': df['carbohydrates'].mean(),
                                    'Fat': df['fat'].mean()
                                }
                                
                                fig_pie = go.Figure(data=[go.Pie(
                                    labels=list(avg_macros.keys()),
                                    values=list(avg_macros.values()),
                                    hole=.3
                                )])
                                
                                fig_pie.update_layout(title='Average Macronutrient Distribution')
                                st.plotly_chart(fig_pie, use_container_width=True)
                                
                                # Display the rest of the analysis
                                st.write("### 📊 Detailed Analysis")
                                
                                st.write("**Macronutrient Patterns:**")
                                for trend in analysis["trend_analysis"]["macronutrient_trends"]:
                                    st.write(f"- {trend}")
                                
                                # Continue with the rest of your existing analysis display...

                            except json.JSONDecodeError:
                                st.error("Error parsing the analysis response. Please try again.")

                            except Exception as e:
                                st.error(f"Error analyzing diet history: {str(e)}")

                except Exception as e:
                    st.error(f"Error analyzing diet history: {str(e)}")
        
        # Save to database
        save_record(
            st.session_state.image_bytes,
            parsed_result['macronutrients'],
            parsed_result['micronutrients'],
            parsed_result['food_items'],
            parsed_result['improvements'],
            goal,
            is_refinement=True,
            custom_timestamp=custom_timestamp
        )

# # Add a section to clear database
# st.header("Database Management")
# if st.button("🗑️ Clear All Records"):
#     try:
#         conn = sqlite3.connect("nutrition_data.db")
#         cursor = conn.cursor()
#         cursor.execute("DROP TABLE IF EXISTS records")
#         conn.commit()
        
#         # Recreate the table
#         cursor.execute('''CREATE TABLE IF NOT EXISTS records (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             image BLOB,
#             timestamp TEXT,
#             macronutrients TEXT,
#             micronutrients TEXT,
#             food_items TEXT,
#             improvements TEXT,
#             goal TEXT
#         )''')
#         conn.commit()
#         conn.close()
        
#         # Clear session state as well
#         if 'analysis_done' in st.session_state:
#             st.session_state.analysis_done = False
#         if 'initial_result' in st.session_state:
#             st.session_state.initial_result = None
#         if 'image_bytes' in st.session_state:
#             st.session_state.image_bytes = None
#         if 'base64_image' in st.session_state:
#             st.session_state.base64_image = None
#         if 'last_uploaded_file' in st.session_state:
#             st.session_state.last_uploaded_file = None
            
#         st.success("✅ Database cleared successfully! You can now start adding new records.")
#         st.rerun()
#     except Exception as e:
#         st.error(f"Error clearing database: {str(e)}")
#         st.write("Debug info:", e)

def display_records():
    try:
        conn = sqlite3.connect("nutrition_data.db")
        cursor = conn.cursor()
        
        # Debug: Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='records'")
        if not cursor.fetchone():
            st.warning("Database table does not exist!")
            return
            
        cursor.execute("SELECT COUNT(*) FROM records")
        count = cursor.fetchone()[0]
        st.write(f"Total records in database: {count}")
        
        cursor.execute("SELECT DISTINCT timestamp, macronutrients, micronutrients, food_items, goal, image FROM records ORDER BY timestamp DESC")
        records = cursor.fetchall()
        conn.close()

        if not records:
            st.info("No records found in the database.")
        else:
            for record in records:
                st.write("---")
                st.write(f"**📅 Timestamp:** {record[0]}")
                
                # Parse and display macronutrients
                macros = json.loads(record[1])
                st.write("**💪 Macronutrients:**")
                for macro, value in macros.items():
                    if macro == 'calories':
                        st.write(f"- {macro.title()}: {value} kcal")
                    elif macro in ['sodium', 'cholesterol']:
                        st.write(f"- {macro.title()}: {value} mg")
                    else:
                        st.write(f"- {macro.title()}: {value}g")
                
                # Parse and display micronutrients
                micros = json.loads(record[2])
                st.write("\n**🥗 Micronutrients:**")
                for micro, value in micros.items():
                    if micro in ['vitamin_a']:
                        st.write(f"- {micro.replace('_', ' ').title()}: {value} IU")
                    elif micro in ['fiber']:
                        st.write(f"- {micro.title()}: {value}g")
                    else:
                        st.write(f"- {micro.replace('_', ' ').title()}: {value} mg")
                
                # Parse and display food items
                foods = json.loads(record[3])
                st.write("\n**🍽️ Foods Identified:**")
                for food in foods:
                    st.write(f"- {food}")
                
                st.write(f"\n**🎯 Goal:** {record[4]}")
                
                # Display the image only once
                if record[5]:  # Check if image exists
                    st.image(record[5], caption="Meal Image", width=700)
                
                st.write("---")
    except Exception as e:
        st.error(f"Error loading records: {str(e)}")        
        st.write("Debug info:", e)

# View saved records with debug information
st.header("View Past Records")
if st.button("Show Records"):
    try:
        conn = sqlite3.connect("nutrition_data.db")
        cursor = conn.cursor()
        
        # Debug: Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='records'")
        if not cursor.fetchone():
            st.warning("Database table does not exist!")
            
        cursor.execute("SELECT COUNT(*) FROM records")
        count = cursor.fetchone()[0]
        st.write(f"Total records in database: {count}")
        
        cursor.execute("SELECT DISTINCT timestamp, macronutrients, micronutrients, food_items, goal, image FROM records ORDER BY timestamp DESC")
        records = cursor.fetchall()
        conn.close()

        if not records:
            st.info("No records found in the database.")
        else:
            for record in records:
                st.write("---")
                st.write(f"**📅 Timestamp:** {record[0]}")
                
                # Parse and display macronutrients
                macros = json.loads(record[1])
                st.write("**💪 Macronutrients:**")
                for macro, value in macros.items():
                    if macro == 'calories':
                        st.write(f"- {macro.title()}: {value} kcal")
                    elif macro in ['sodium', 'cholesterol']:
                        st.write(f"- {macro.title()}: {value} mg")
                    else:
                        st.write(f"- {macro.title()}: {value}g")
                
                # Parse and display micronutrients
                micros = json.loads(record[2])
                st.write("\n**🥗 Micronutrients:**")
                for micro, value in micros.items():
                    if micro in ['vitamin_a']:
                        st.write(f"- {micro.replace('_', ' ').title()}: {value} IU")
                    elif micro in ['fiber']:
                        st.write(f"- {micro.title()}: {value}g")
                    else:
                        st.write(f"- {micro.replace('_', ' ').title()}: {value} mg")
                
                # Parse and display food items
                foods = json.loads(record[3])
                st.write("\n**🍽️ Foods Identified:**")
                for food in foods:
                    st.write(f"- {food}")
                
                st.write(f"\n**🎯 Goal:** {record[4]}")
                
                # Display the image
                if record[5]:  # Check if image exists
                    st.image(record[5], caption=f"Meal Image - {record[0]}", width=700)
                
                st.write("---")
    except Exception as e:
        st.error(f"Error loading records: {str(e)}")
        st.write("Debug info:", e)