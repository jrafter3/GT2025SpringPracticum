import time
import httpx
from anthropic import Anthropic

class ClaudeLLM:
    """Handles Abthropic Claude AI requests"""

    def __init__(self):
        self.client = Anthropic(api_key="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")

    def summarize_modification(self, original_text, modified_text, section_id):
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

        print(f"📝 Calling LLM to summarize modifications for {section_id}...")
        start_time = time.time()

        if not original_text or not modified_text:
            return "No valid U.S. Code or bill text found."

        prompt = f"""
        A proposed bill modifies the following section of the U.S. Code:
        **Original U.S. Code Section ({section_id}):**
        {original_text}
        **Modified Bill Text:**
        {modified_text}
        **Instructions:**
        - Summarize key legal changes.
        - Assign a **Relevance Score (0-100%)**.

        **Return format:**
        {{
            "change_type": "Minor | Moderate | Major",
            "summary_of_changes": ["Point 1", "Point 2"],
            "legal_impact": "Description of consequences",
            "relevance_score": 0-100,
            "relevance_explanation": "Explanation here"
        }}
        """

        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-latest",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            print(f"✅ LLM analysis completed in {time.time() - start_time:.2f} seconds.")
            return response.content

        except Exception as e:
            print(f"AI API error: {e}")
            return "AI analysis failed."
