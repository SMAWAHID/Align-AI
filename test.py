import google.generativeai as genai

genai.configure(api_key="AIzaSyBl46Si1djh2s0g0g6EUaQEmsRIMDZHFXo")

# Convert generator to list
models = list(genai.list_models())
print(models)