import streamlit as st
import requests
from PIL import Image
import io
import datetime
import sqlite3
import base64
import os
import openai
import json
from dotenv import load_dotenv

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
    Initialize database with all required columns.
    If table exists, drop it and recreate with the correct schema.
    """
    try:
        conn = sqlite3.connect("nutrition_data.db")
        cursor = conn.cursor()
        
        # Drop existing table if it exists
        cursor.execute('''DROP TABLE IF EXISTS records''')
        
        # Create new table with all required columns
        cursor.execute('''CREATE TABLE records (
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

def save_record(image, macronutrients, micronutrients, food_items, improvements, goal):
    try:
        conn = sqlite3.connect("nutrition_data.db")
        cursor = conn.cursor()
        
        # Convert data to JSON strings for storage
        macronutrients_json = json.dumps(macronutrients)
        micronutrients_json = json.dumps(micronutrients)
        food_items_json = json.dumps(food_items)
        improvements_json = json.dumps(improvements)
        
        cursor.execute("""
            INSERT INTO records (image, timestamp, macronutrients, micronutrients, food_items, improvements, goal) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            image, 
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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

# Initialize OpenAI API key
api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    st.error("OpenAI API key is not set. Please check your .env file.")
    st.stop()
    
# Set the API key directly
#openai.api_key = api_key
client = OpenAI(api_key=api_key)

# Function to analyze image with OpenAI
def analyze_image_with_image_recognition(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": """Analyze the food items in this image and provide the nutritional information in the following JSON format only:
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
            "suggestion 1",
            "suggestion 2",
            ...
        ],
        "context": "brief explanation of why these improvements are suggested based on the goal"
    }
}
Consider the user's goal when suggesting improvements. Provide only the JSON response without any additional text or explanation."""
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ],
        }
    ],
    max_tokens=300,
    )
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
    # Create a copy to avoid modifying original
    img_copy = image.copy()
    
    # Resize using LANCZOS resampling
    img_copy.thumbnail(max_size, Image.LANCZOS)
    
    # Compress and convert to bytes
    image_bytes = io.BytesIO()
    img_copy.save(image_bytes, format='JPEG', quality=quality)
    
    return image_bytes.getvalue()


# # Initialize database
init_db()

# # Streamlit UI
st.title("Macronutrient Counter")
st.sidebar.header("Your Goal")
goal = st.sidebar.radio("Select your goal:", ["Maintain weight", "Fat loss", "Weight gain"])

st.header("Upload Food Image")
uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])


# Update the main UI section where results are displayed
if uploaded_file:
    # Clear session state when a new image is uploaded
    if 'last_uploaded_file' not in st.session_state or st.session_state.last_uploaded_file != uploaded_file.name:
        st.session_state.analysis_done = False
        st.session_state.initial_result = None
        st.session_state.image_bytes = None
        st.session_state.base64_image = None
        st.session_state.last_uploaded_file = uploaded_file.name
    
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image", use_column_width=True)

    # First Analysis Button
    if not st.session_state.analysis_done and st.button("Analyze Image"):
        image_bytes = process_image_for_analysis(image)
        st.session_state.image_bytes = image_bytes
        st.session_state.base64_image = base64.b64encode(image_bytes).decode("utf-8")
        
        # Initial analysis
        result = analyze_image_with_image_recognition(image_bytes)
        message_content = result.choices[0].message.content
        st.session_state.initial_result = parse_nutrition_response(message_content)
        st.session_state.analysis_done = True
        st.rerun()

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
            "suggestion 1",
            "suggestion 2"
        ],
        "context": "brief explanation of why these improvements are suggested based on the goal"
    }}
}}'''

                    # Update the analyze function to include meal description
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": prompt_text
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/jpeg;base64,{st.session_state.base64_image}"},
                                    },
                                ],
                            }
                        ],
                        max_tokens=500,
                    )
                    # Update parsed result with refined analysis
                    parsed_result = parse_nutrition_response(response.choices[0].message.content)
                    st.session_state.initial_result = parsed_result
                    st.success("Analysis refined successfully!")
                    
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
        
        # Save to database
        save_record(
            st.session_state.image_bytes,
            parsed_result['macronutrients'],
            parsed_result['micronutrients'],
            parsed_result['food_items'],
            parsed_result['improvements'],
            goal
        )

# View saved records
st.header("View Past Records")
if st.button("Show Records"):
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, macronutrients, food_items, goal, image FROM records")
    records = cursor.fetchall()
    conn.close()

    for record in records:
        st.write(f"**Timestamp:** {record[0]}")
        
        # Parse and display macronutrients
        macros = json.loads(record[1])
        st.write("**Macronutrients:**")
        st.write(f"- Carbohydrates: {macros['carbohydrates']}g")
        st.write(f"- Protein: {macros['protein']}g")
        st.write(f"- Fat: {macros['fat']}g")
        
        # Parse and display food items
        foods = json.loads(record[2])
        st.write("**Foods Identified:**")
        for food in foods:
            st.write(f"- {food}")
            
        st.write(f"**Goal:** {record[3]}")
        # Display the image
        image_data = record[4]
        st.image(image_data, caption="Saved Image", use_column_width=True)
        st.write("---")