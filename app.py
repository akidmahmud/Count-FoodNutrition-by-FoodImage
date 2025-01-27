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
        st.write("Cleaned response:", cleaned_response)
        
        # Parse JSON response
        data = json.loads(cleaned_response)
        
        return {
            'food_items': data['identified_foods'],
            'macronutrients': data['macronutrients'],
            'micronutrients': data['micronutrients'],
            'improvements': data['improvements']
        }
    except Exception as e:
        st.error(f"Error parsing nutrition data: {str(e)}")
        st.write(f"Exception details: {str(e)}")
        return {
            'food_items': [],
            'macronutrients': {'carbohydrates': 0, 'protein': 0, 'fat': 0},
            'micronutrients': {'vitamin_a': 0, 'vitamin_c': 0, 'calcium': 0, 'iron': 0, 'fiber': 0},
            'improvements': {'suggestions': [], 'context': ''}
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
        
        # Verify the schema
        check_db_schema()
        
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
openai.api_key = api_key

# Function to analyze image with OpenAI
def analyze_image_with_image_recognition(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    response = openai.ChatCompletion.create(
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
        "fat": number
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

# # Add this line after your init_db() call to check the schema
check_db_schema()

# # Streamlit UI
st.title("Macronutrient Counter")
st.sidebar.header("Your Goal")
goal = st.sidebar.radio("Select your goal:", ["Maintain weight", "Fat loss", "Weight gain"])

st.header("Upload Food Image")
uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])


# Update the main UI section where results are displayed
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image", use_column_width=True)

    if st.button("Analyze Image"):
        image_bytes = process_image_for_analysis(image)
        
        # Analyze the image using OpenAI
        result = analyze_image_with_image_recognition(image_bytes)
        message_content = result.choices[0].message.content
        
        # Parse the response
        parsed_result = parse_nutrition_response(message_content)
        
        # Create tabs
        tab1, tab2, tab3 = st.tabs(["Macronutrients", "Micronutrients", "Suggestions"])
        
        with tab1:
            st.subheader("Macronutrients Analysis")
            st.write("Identified Foods:")
            for food in parsed_result['food_items']:
                st.write(f"- {food}")
                
            st.write("\nMacronutrients:")
            st.write(f"- Carbohydrates: {parsed_result['macronutrients']['carbohydrates']}g")
            st.write(f"- Protein: {parsed_result['macronutrients']['protein']}g")
            st.write(f"- Fat: {parsed_result['macronutrients']['fat']}g")
        
        with tab2:
            st.subheader("Micronutrients Analysis")
            st.write(f"- Vitamin A: {parsed_result['micronutrients']['vitamin_a']}IU")
            st.write(f"- Vitamin C: {parsed_result['micronutrients']['vitamin_c']}mg")
            st.write(f"- Calcium: {parsed_result['micronutrients']['calcium']}mg")
            st.write(f"- Iron: {parsed_result['micronutrients']['iron']}mg")
            st.write(f"- Fiber: {parsed_result['micronutrients']['fiber']}g")
        
        with tab3:
            st.subheader("Suggested Improvements")
            st.write("Based on your goal:", goal)
            for suggestion in parsed_result['improvements']['suggestions']:
                st.write(f"- {suggestion}")
            st.write("\nContext:")
            st.write(parsed_result['improvements']['context'])
        
        # Save to database with all required arguments
        save_record(
            image_bytes,
            parsed_result['macronutrients'],
            parsed_result['micronutrients'],
            parsed_result['food_items'],
            parsed_result['improvements'],
            goal
        )
        
        st.success("Analysis saved successfully!")

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