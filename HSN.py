import streamlit as st
import pandas as pd
import difflib
import datetime
from collections import Counter

# Simple password to access the admin features like uploading new data
ADMIN_PASSWORD = "admin123"

# Function to load a specified sheet from the default Excel file and cache it
def load_hsn_data(sheet_name=0):
    session_key = f"hsn_data_sheet_{sheet_name}"
    if session_key in st.session_state:
        return st.session_state[session_key]
    else:
        try:
            df = pd.read_excel("HSN_SAC.xlsx", sheet_name=sheet_name)
            df.columns = df.columns.str.strip()
            st.session_state[session_key] = df
            return df
        except Exception as e:
            st.error(f"Error loading Excel file sheet {sheet_name}: {e}")
            st.stop()

# Function to load both sheets from the uploaded file and cache them
def upload_hsn_file(uploaded_file):
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet_names = xls.sheet_names
        st.write(f"Uploaded file sheets: {sheet_names}")

        df_hsn = pd.read_excel(xls, sheet_name=0)
        df_sac = pd.read_excel(xls, sheet_name=1)

        df_hsn.columns = df_hsn.columns.str.strip()
        df_sac.columns = df_sac.columns.str.strip()

        st.session_state["hsn_data_sheet_0"] = df_hsn
        st.session_state["hsn_data_sheet_1"] = df_sac

        st.success(f"HSN Master Data uploaded successfully! ({uploaded_file.name})")
        st.session_state.invalid_codes_log = []
        st.session_state.last_update = datetime.datetime.now()
    except Exception as e:
        st.error(f"Failed to load uploaded file: {e}")

# Validator that checks codes against both sheets
class HSNValidator:
    def __init__(self, hsn_df, sac_df):
        self.hsn_df = hsn_df
        self.sac_df = sac_df
        self.valid_lengths = [2, 4, 6, 8]
        self.hsn_codes_set = set(self.hsn_df['HSNCode'].astype(str).values)
        self.sac_codes_set = set(self.sac_df['SAC_CD'].astype(str).values)

    def validate_code_format(self, code):
        if not code.isdigit():
            return False, "Must be numeric"
        if len(code) not in self.valid_lengths:
            return False, f"Length must be 2, 4, 6, or 8 digits (got {len(code)})"
        return True, ""

    def code_exists(self, code):
        return code in self.hsn_codes_set or code in self.sac_codes_set

    def get_code_description(self, code):
        if code in self.hsn_codes_set:
            desc = self.hsn_df.loc[self.hsn_df['HSNCode'].astype(str) == code, 'Description'].values
            return desc[0] if len(desc) > 0 else "No description available."
        elif code in self.sac_codes_set:
            # FIX: Use 'SAC_Description' column for SAC codes
            if 'SAC_Description' in self.sac_df.columns:
                desc = self.sac_df.loc[self.sac_df['SAC_CD'].astype(str) == code, 'SAC_Description'].values
                return desc[0] if len(desc) > 0 else "No description available."
            else:
                return "SAC Code exists, but no description available."
        else:
            return "No description available."

    def check_hierarchy(self, code):
        results = []
        for length in self.valid_lengths:
            if len(code) >= length:
                prefix = code[:length]
                exists = prefix in self.hsn_codes_set or prefix in self.sac_codes_set
                results.append((prefix, exists))
        return results

    def suggest_similar_codes(self, code, n=3):
        all_codes = list(self.hsn_codes_set.union(self.sac_codes_set))
        close_matches = difflib.get_close_matches(code, all_codes, n=n, cutoff=0.6)
        return close_matches

    def process_input(self, user_input):
        user_input = user_input.strip()
        if user_input.lower() in ["help", "?"]:
            return (
                "📝 **HSN Code Validation Help**:\n"
                "- Enter one or more HSN or SAC codes separated by commas.\n"
                "- Codes must be numeric with length 2, 4, 6, or 8.\n"
                "- Example: `1001, 123456, 99887766`\n"
                "- You can upload a new HSN master file in Admin Panel.\n"
            )

        codes = [c.strip() for c in user_input.split(",") if c.strip()]
        responses = []

        for code in codes:
            is_valid_format, reason = self.validate_code_format(code)
            if not is_valid_format:
                msg = f"❌ Code '{code}': Invalid format - {reason}."
                responses.append(msg)
                log_invalid_code(code, reason)
                continue

            if not self.code_exists(code):
                msg = f"❌ Code '{code}': Not found in master data."
                suggestions = self.suggest_similar_codes(code)
                if suggestions:
                    msg += f" Did you mean: {', '.join(suggestions)}?"
                responses.append(msg)
                log_invalid_code(code, "Not found")
                continue

            desc = self.get_code_description(code)
            hierarchy = self.check_hierarchy(code)
            hier_text = "\n".join(
                [f"  {prefix} → {'✅ Exists' if exists else '❌ Not found'}" for prefix, exists in hierarchy]
            )

            response = (
                f"✅ Code '{code}' is valid.\n"
                f"📄 Description: {desc}\n"
                f"🔍 Hierarchy Check:\n{hier_text}"
            )
            responses.append(response)

        return "\n\n".join(responses)

def log_invalid_code(code, reason):
    if "invalid_codes_log" not in st.session_state:
        st.session_state.invalid_codes_log = []
    st.session_state.invalid_codes_log.append((code, reason))

def display_chat():
    for chat in st.session_state.history:
        message_html = chat["message"].replace("\n", "<br>")
        if chat["is_user"]:
            st.markdown(
                f'<div style="text-align: right; background-color: #d1e7dd; color: #0f5132; padding: 10px; '
                f'border-radius: 10px; margin: 5px; border: 1px solid #badbcc; '
                f'max-width: 80%; margin-left: auto; font-family: Arial, sans-serif; font-size: 14px;">{message_html}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="text-align: left; background-color: #e2e3e5; color: #41464b; padding: 10px; '
                f'border-radius: 10px; margin: 5px; border: 1px solid #d3d6d8; '
                f'max-width: 80%; font-family: Arial, sans-serif; font-size: 14px;">{message_html}</div>',
                unsafe_allow_html=True,
            )

st.set_page_config(page_title="HSN Code Validation Chatbot", layout="centered")
st.title("🛠️ Interactive HSN Code Validation Chatbot")

# Load data sheets
df_hsn = load_hsn_data(sheet_name=0)
df_sac = load_hsn_data(sheet_name=1)

validator = HSNValidator(df_hsn, df_sac)

if "history" not in st.session_state:
    st.session_state.history = []

if "last_update" not in st.session_state:
    st.session_state.last_update = None

with st.sidebar:
    st.header("Admin Panel 🔐")
    password_input = st.text_input("Enter admin password to upload data:", type="password")

    if password_input == ADMIN_PASSWORD:
        uploaded_file = st.file_uploader("Upload new HSN Master Excel file", type=["xls", "xlsx"])
        if uploaded_file is not None:
            upload_hsn_file(uploaded_file)

        st.markdown("---")
        st.subheader("Data Quality Dashboard 📊")
        if "invalid_codes_log" in st.session_state and st.session_state.invalid_codes_log:
            st.write(f"**Invalid codes logged:** {len(st.session_state.invalid_codes_log)}")
            counter = Counter([code for code, _ in st.session_state.invalid_codes_log])
            top5 = counter.most_common(5)
            st.write("Most frequent invalid codes:")
            for code, freq in top5:
                st.write(f"- `{code}`: {freq} times")
        else:
            st.write("No invalid codes logged yet.")

        if st.session_state.last_update:
            st.write(f"Last data update: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.write("Data loaded from default source.")
    else:
        st.write("Admin login required to upload new data or view dashboard.")

def submit_message():
    user_message = st.session_state.user_input.strip()
    if user_message:
        st.session_state.history.append({"message": user_message, "is_user": True})
        response = validator.process_input(user_message)
        st.session_state.history.append({"message": response, "is_user": False})
        st.session_state.user_input = ""

st.text_input(
    "Enter HSN or SAC code(s) (comma separated), or type 'help' for usage instructions:",
    key="user_input",
    on_change=submit_message
)

display_chat()

if st.session_state.last_update:
    st.caption(f"📅 Data last updated on: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
else:
    st.caption("📅 Data loaded from default master file.")
