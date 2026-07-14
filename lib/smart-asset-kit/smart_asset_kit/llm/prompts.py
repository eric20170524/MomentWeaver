class Prompts:
    @staticmethod
    def enhance_image_prompt(original_prompt: str) -> str:
        return (
            "You are an expert game and film concept artist. "
            "Please enhance the following brief description into a professional, highly-detailed image generation prompt. "
            "Include aspects like lighting (e.g. volumetric lighting, rim light), camera angle, artistic style, and rendering engine details (e.g. Unreal Engine 5 render, ray tracing). "
            "Output ONLY the final English prompt, without any conversational text or formatting like markdown code blocks.\n\n"
            f"Original Description: {original_prompt}"
        )
