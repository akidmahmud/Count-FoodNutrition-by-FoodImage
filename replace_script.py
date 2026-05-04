import os

filepath = r"c:\Users\akidm\Desktop\Work-Cal\FoodNutrition-AI\app.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Chunk 1
content = content.replace("""import openai
import json
from dotenv import load_dotenv""", """import google.generativeai as genai
import json
from dotenv import load_dotenv""")

# Chunk 2
old_chunk2 = """# Initialize OpenAI API key
api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    st.error("OpenAI API key is not set. Please check your .env file.")
    st.stop()
    
# Set the API key directly
openai.api_key = api_key"""
new_chunk2 = """# Initialize Gemini API key
api_key = os.getenv('GEMINI_API_KEY') or os.getenv('OPENAI_API_KEY')
if not api_key:
    st.error("API key is not set. Please check your .env file.")
    st.stop()
    
# Set the API key directly
genai.configure(api_key=api_key)"""
content = content.replace(old_chunk2, new_chunk2)

# Chunk 3
old_chunk3 = """def analyze_image_with_image_recognition(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = openai.ChatCompletion.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": \"\"\"Analyze the food items in this image and provide the nutritional information in the following JSON format only:
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
Consider the user's goal when suggesting improvements. Be encouraging when healthy choices are present. Provide only the JSON response without any additional text or explanation.\"\"\"
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
    return response"""

new_chunk3 = """def analyze_image_with_image_recognition(image_bytes):
    prompt_text = \"\"\"Analyze the food items in this image and provide the nutritional information in the following JSON format only:
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
Consider the user's goal when suggesting improvements. Be encouraging when healthy choices are present. Provide only the JSON response without any additional text or explanation.\"\"\"

    img = Image.open(io.BytesIO(image_bytes))
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([prompt_text, img])
    return response"""
content = content.replace(old_chunk3, new_chunk3)

# Chunk 4
old_chunk4 = """                result = analyze_image_with_image_recognition(image_bytes)
                message_content = result.choices[0].message.content"""
new_chunk4 = """                result = analyze_image_with_image_recognition(image_bytes)
                message_content = result.text"""
content = content.replace(old_chunk4, new_chunk4)


# Chunk 5
old_chunk5 = """                    # Update the analyze function to include meal description
                    response = openai.ChatCompletion.create(
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
                    parsed_result = parse_nutrition_response(response.choices[0].message.content)"""

new_chunk5 = """                    # Update the analyze function to include meal description
                    img_bytes = base64.b64decode(st.session_state.base64_image)
                    img = Image.open(io.BytesIO(img_bytes))
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content([prompt_text, img])
                    # Update parsed result with refined analysis
                    parsed_result = parse_nutrition_response(response.text)"""
content = content.replace(old_chunk5, new_chunk5)

# Chunk 6
old_chunk6 = """                        # Call OpenAI for analysis
                        with st.spinner("🔄 Analyzing your diet history..."):
                            response = openai.ChatCompletion.create(
                                model="gpt-4",
                                messages=[
                                    {
                                        "role": "user",
                                        "content": f\"\"\"Analyze the following diet history and provide a comprehensive nutritional analysis. 
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
                                        }}\"\"\"
                                    }
                                ],
                                max_tokens=1000
                            )

                            try:
                                analysis = json.loads(response.choices[0].message.content)"""

new_chunk6 = """                        # Call Gemini for analysis
                        with st.spinner("🔄 Analyzing your diet history..."):
                            prompt_text = f\"\"\"Analyze the following diet history and provide a comprehensive nutritional analysis. 
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
                                        }}\"\"\"
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            response = model.generate_content(prompt_text)

                            try:
                                analysis_text = response.text.replace("```json", "").replace("```", "").strip()
                                analysis = json.loads(analysis_text)"""

content = content.replace(old_chunk6, new_chunk6)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Done replacing.")
