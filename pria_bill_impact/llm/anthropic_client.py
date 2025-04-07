import time
import httpx
from anthropic import Anthropic
import json

class ClaudeLLM:
    """Handles Abthropic Claude AI requests"""

    def __init__(self):
        self.client = Anthropic(api_key="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")


        #Can sub model with claude-3-haiku-20240307, claude-3-opus-latest
    def call_claude_llm(self, prompt, model="claude-3-haiku-20240307", max_retries=3):
        """
        Calls Claude LLM API with robust error handling, including rate limits.
        
        Args:
            prompt (str): The input prompt for the LLM.
            model (str): Claude model to use.
            max_retries (int): Maximum retries in case of failure.

        Returns:
            str: The response content from Claude, or an error message if it fails.
        """
        attempt = 0
        start_time = time.time()

        while attempt < max_retries:
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                print(f"LLM analysis completed in {time.time() - start_time:.2f} seconds.")
                return response.content  #  Return response if successful

            except Exception as e:
                error_msg = str(e).lower()

                # Detect Rate Limit Error
                if "rate limit" in error_msg or "limit per minute" in error_msg:
                    print(f"⏳ API rate limit exceeded. Waiting 60 seconds before retrying... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(60)  # ⏳ Pause for 60 seconds
                    attempt += 1
                    continue

                # Handle Other API Errors
                print(f"AI API error: {e} (Attempt {attempt + 1}/{max_retries})")
                attempt += 1
                time.sleep(5)  # Small delay before retrying non-rate-limit errors

        return "AI analysis failed after multiple retries."


    def summarize_modification(self, original_text, modified_text, section_id, became_law):
        """
        Uses Claude Haiku LLM to summarize the modification impact. One of the key parts of this
        function is the Instructions we give to Claude and the return format we ask of it. This can
        be modified.

        Args:
            original_text (str): The original U.S. Code section text.
            modified_text (str): The "modification" of the code, which is Bill text. This is
                                 either bill text for a bill that has passed into law and we match
                                 exactly with the U.S. code section we know it's modified, or the 
                                 closest identified U.S. code section for Bills that aren't yet
                                 passed. 
            section_id (str): The identifier of the U.S. Code section.

        Returns:
            TextBlock: The response from the Claude API containing the summary.
            If an error occurs, returns None.
        """

        print(f"Calling LLM to summarize modifications for {section_id}...")
        start_time = time.time()

        if not original_text or not modified_text:
            return "No valid U.S. Code or bill text found."

        passed_status = "has already become law" if became_law else "has not yet passed into law"

        prompt = f"""
        A proposed bill modifies the following section of the U.S. Code.
        This bill {passed_status}.

        **Original U.S. Code Section ({section_id}):**
        {original_text}

        **Modified Bill Text:**
        {modified_text}

        **Instructions:**
        - Summarize key legal changes.
        - Assign a **Relevance Score (0-10)**.
        - If the bill has already passed into law, provide an exact "before" and "after" comparison of the U.S. Code.
        - If it has not yet passed, predict how it might change the U.S. Code.

        **Return format:**
        {{
            "change_type": "Minor | Moderate | Major",
            "summary_of_changes": ["Point 1", "Point 2"],
            "legal_impact": "Description of consequences",
            "relevance_score": 0-10,
            "relevance_explanation": "Explanation here",
            "before_and_after": {{
                "before": "Text before modification",
                "after": "Text after modification (or predicted change)"
            }}
        }}
        """

        return self.call_claude_llm(prompt)



    def identify_affected_demographics(self, bill_text, matched_us_code_sections):
        print("📝 Asking LLM to identify affected demographic groups...")

        # Load demographic groups and rubrics
        with open("data/demographic_data.json", "r") as f:
            demographic_data = json.load(f)

        with open("data/demographic_rubrics.json", "r") as f:
            rubric_templates = json.load(f)

        demographic_blocks = []
        for category, subgroups in demographic_data.items():
            rubric_key = category if isinstance(subgroups, dict) and "_rubric_group" not in subgroups else subgroups.get("_rubric_group")
            rubric = rubric_templates.get(rubric_key, "")
            for subgroup in subgroups:
                if subgroup == "_rubric_group":
                    continue
                demographic_blocks.append(f'"{category} - {subgroup}": "Use the following rubric to evaluate impact:\n{rubric}"')

        rubric_prompt = "\n\n".join(demographic_blocks)

        matched_sections_str = "\n".join([section["section_id"] for section in matched_us_code_sections])

        prompt = f"""
        A bill has been introduced that modifies sections of the U.S. Code.

        **Bill Text:**
        {bill_text}

        **Relevant U.S. Code Sections:**
        {matched_sections_str}

        **Instructions:**

        You are tasked with evaluating the impact of this bill on a wide range of demographic groups.

        Follow these steps:

        1. **Score Every Group**:
           - For each demographic group listed below, evaluate how this bill would materially affect individuals in that group.
           - Assign an **impact score between -5 and 5**, based strictly on the rubric provided for that group.
           - Do not skip any groups, and do not rely on assumptions or generalizations outside the rubric.
           - Focus only on direct or pseudo-financial impacts (e.g. taxes, benefits, access to services) — ignore symbolic, cultural, or indirect effects.

        2. **Rank the Results**:
           - After scoring all groups, rank them by the **absolute value** of their impact scores (whether positive or negative).

        3. **Return Only the Top 5**:
           - Select the 5 demographic groups with the most extreme (highest absolute value) impact scores.
           - Return exactly 5 groups in your final JSON output — no more, no less.

        4. **Estimate Financial Impact** (Optional):
           - If applicable, include a rough estimate of the individual financial impact (in dollars per year) for that demographic group.
           - Format this as a simple number or range (e.g. "$2,000/year" or "$1,000–$3,000/year").
           - Leave blank if there's no meaningful financial impact.

        Do **not** include any demographic groups not listed below.

        ---

        **Demographic Groups and Rubrics:**
        {rubric_prompt}

        ---

        **Return Format (JSON):**
        A JSON object with exactly 5 entries in the following format:
        {{
           "Group 1 Name": { ... },
           "Group 2 Name": { ... },
           "Group 3 Name": { ... },
           "Group 4 Name": { ... },
           "Group 5 Name": { ... }
        }}

        **Example Output:**
        {{
          "Race - White": {{
            "impact_score": 2,
            "justification": "The bill slightly expands protections for this group under existing anti-discrimination funding clauses.",
            "estimated_monetary_impact": "-$2,000/year per affected person (loss of subsidies and services)"
          }},
          "Housing - Renters": {{
            "impact_score": 4,
            "justification": "The bill includes significant new rental assistance that lowers costs for renters.",
            "estimated_monetary_impact": ""
          }}
        }}
        """


        return self.call_claude_llm(prompt)







