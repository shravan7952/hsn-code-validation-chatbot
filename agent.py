import pandas as pd
import difflib
import os
from google.adk.agents import Agent

print(f"[DEBUG] Current working directory: {os.getcwd()}")

# Load the Excel file using absolute path
def load_hsn_data(sheet_name=0):
    try:
        excel_path = os.path.join(os.path.dirname(__file__), "HSN_SAC.xlsx")
        df = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str) # Load all as string
        df.columns = df.columns.str.strip() # Strip whitespace from column names
        print(f"[ADK - LOAD] Loaded columns from sheet {sheet_name}: {df.columns.tolist()}")
        return df
    except Exception as e:
        print(f"[ADK - LOAD ERROR] Error loading Excel file sheet {sheet_name}: {e}")
        return pd.DataFrame()

# Load sheets (load globally for local testing)
df_hsn_global = load_hsn_data(sheet_name=0)
df_sac_global = load_hsn_data(sheet_name=1)

# Validator class
class HSNValidator:
    def __init__(self, hsn_df, sac_df):
        self.hsn_df = hsn_df
        self.sac_df = sac_df
        self.valid_lengths = [2, 4, 6, 8]
        self.hsn_codes_set = set(self.hsn_df['HSNCode'].str.strip().str.upper().tolist()) if 'HSNCode' in self.hsn_df.columns else set()
        self.sac_codes_set = set(self.sac_df['SAC_CD'].str.strip().str.upper().tolist()) if 'SAC_CD' in self.sac_df.columns else set()
        self.hsn_description_map = self.hsn_df.set_index(self.hsn_df['HSNCode'].str.strip().str.upper())['Description'].to_dict() if 'HSNCode' in self.hsn_df.columns and 'Description' in self.hsn_df.columns else {}
        self.sac_description_map = self.sac_df.set_index(self.sac_df['SAC_CD'].str.strip().str.upper())['SAC_Description'].to_dict() if 'SAC_CD' in self.sac_df.columns and 'SAC_Description' in self.sac_df.columns else {}

    def validate_code_format(self, code):
        if not code.isdigit():
            return False, "Must be numeric"
        if len(code) not in self.valid_lengths:
            return False, f"Length must be 2, 4, 6, or 8 digits (got {len(code)})"
        return True, ""

    def code_exists(self, code):
        processed_code = code.strip().upper()
        return processed_code in self.hsn_codes_set or processed_code in self.sac_codes_set

    def get_code_description(self, code):
        processed_code = code.strip().upper()
        if processed_code in self.hsn_codes_set:
            return self.hsn_description_map.get(processed_code, "Description not found.")
        elif processed_code in self.sac_codes_set:
            return self.sac_description_map.get(processed_code, "Description not found.")
        return "Code not found."

    def check_hierarchy(self, code):
        processed_code = code.strip().upper()
        results = []
        for length in self.valid_lengths:
            if len(processed_code) >= length:
                prefix = processed_code[:length]
                exists = prefix in self.hsn_codes_set or prefix in self.sac_codes_set
                results.append((prefix, exists))
        return results

    def suggest_similar_codes(self, code, n=3):
        processed_code = code.strip().upper()
        all_codes = list(self.hsn_codes_set.union(self.sac_codes_set))
        close_matches = difflib.get_close_matches(processed_code, all_codes, n=n, cutoff=0.6)
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
                responses.append(f"❌ Code '{code}': Invalid format - {reason}.")
                continue

            if not self.code_exists(code):
                msg = f"❌ Code '{code}': Not found in master data."
                suggestions = self.suggest_similar_codes(code)
                if suggestions:
                    msg += f" Did you mean: {', '.join(suggestions)}?"
                responses.append(msg)
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

# Create validator instance (using globally loaded data for local)
validator = HSNValidator(df_hsn_global, df_sac_global)

# Tool for ADK
def validate_code_tool(code_to_validate: str) -> str:
    """Validates the given HSN or SAC code and provides information."""
    return validator.process_input(code_to_validate)

# ADK Agent definition
root_agent = Agent(
    name="hsn_sac_validator_agent",
    model="gemini-2.0-flash",
    description="Agent to validate HSN and SAC codes.",
    instruction="You are a helpful agent that can validate HSN and SAC codes provided by the user.",
    tools=[validate_code_tool],
)

# Only run prompt loop if NOT in ADK
if __name__ == "__main__":
    while True:
        user_input = input("Enter HSN or SAC code(s) (comma separated), or type 'help' for usage instructions: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        response = validate_code_tool(user_input)
        print(response)