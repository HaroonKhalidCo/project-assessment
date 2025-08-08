from google import genai
from google.genai import types
import asyncio
import os
from typing import Optional

class GeminiDocEvaluator:
    def __init__(self):
        self.client = genai.Client()

    async def evaluate(
        self, 
        file_path: str, 
        step_name: str,
        deliverable_name: str,
        additional_context: Optional[str] = None,
        model: str = "gemini-2.5-flash"
    ) -> str:
        """
        Evaluate a file based on the specified step and deliverable criteria.
        
        Args:
            file_path: Path to the file to evaluate
            step_name: Name of the step being evaluated (e.g., 'Research & Data Collection')
            deliverable_name: Name of the deliverable being evaluated (e.g., 'Survey Results')
            additional_context: Any additional context about the submission
            model: The Gemini model to use for evaluation
            
        Returns:
            str: The evaluation result in markdown format
            
        Raises:
            Exception: If file upload or evaluation fails
        """
        loop = asyncio.get_event_loop()
        myfile = None
        
        try:
            # 1. Verify file exists and is readable
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
                
            # 2. Upload file asynchronously with retry and wait for processing
            max_retries = 3
            retry_delay = 2  # seconds
            max_processing_time = 30  # Maximum time to wait for processing (seconds)
            
            for attempt in range(max_retries):
                try:
                    # Upload the file
                    myfile = await loop.run_in_executor(
                        None, 
                        lambda: self.client.files.upload(file=file_path)
                    )
                    
                    if not hasattr(myfile, 'state'):
                        # If state isn't available, assume it's ready
                        break
                        
                    # Wait for the file to be processed
                    start_time = asyncio.get_event_loop().time()
                    while myfile.state == 'PROCESSING':
                        if (asyncio.get_event_loop().time() - start_time) > max_processing_time:
                            raise Exception(f"File processing timed out after {max_processing_time} seconds")
                        await asyncio.sleep(retry_delay)
                        
                        # Refresh file status
                        myfile = await loop.run_in_executor(
                            None,
                            lambda: self.client.files.get(name=myfile.name)
                        )
                    
                    if myfile.state != 'ACTIVE':
                        raise Exception(f"File is not in ACTIVE state after upload. State: {myfile.state}")
                        
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if attempt == max_retries - 1:  # Last attempt
                        # If we have a file handle, try to clean it up
                        if 'myfile' in locals() and hasattr(myfile, 'name'):
                            try:
                                await loop.run_in_executor(
                                    None,
                                    lambda: self.client.files.delete(name=myfile.name)
                                )
                            except:
                                pass  # Ignore cleanup errors
                        raise Exception(f"Failed to upload file after {max_retries} attempts: {str(e)}")
                    
                    await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            
            if not myfile:
                raise Exception("File upload failed: No file handle returned")
            
            # 3. Create evaluation prompt
            evaluation_prompt = self._create_evaluation_prompt(
                step_name=step_name,
                deliverable_name=deliverable_name,
                additional_context=additional_context
            )
            
            # 4. Generate content asynchronously with error handling
            def generate():
                try:
                    return self.client.models.generate_content(
                        model=model,
                        contents=[evaluation_prompt, myfile]
                    )
                except Exception as e:
                    raise Exception(f"Content generation failed: {str(e)}")
            
            response = await loop.run_in_executor(None, generate)
            
            if not response or not hasattr(response, 'text'):
                raise Exception("Invalid response from Gemini API")
                
            return response.text
            
        except Exception as e:
            raise Exception(f"Evaluation failed: {str(e)}")
            
        finally:
            # 5. Clean up: Delete the file from Gemini if it was uploaded
            if myfile and hasattr(myfile, 'name'):
                try:
                    await loop.run_in_executor(
                        None, 
                        lambda: self.client.files.delete(name=myfile.name)
                    )
                except Exception as cleanup_error:
                    # Log the error but don't fail the main operation
                    print(f"Warning: Failed to delete uploaded file: {str(cleanup_error)}")
    
    def _create_evaluation_prompt(self, step_name: str, deliverable_name: str, additional_context: Optional[str] = None) -> str:
        """Create a detailed prompt for evaluation based on the step and deliverable."""
        base_prompt = f"""
        You are an expert evaluator for the EAD (Early Age Development) project assessment.
        
        **TASK**: Evaluate the provided submission based on the following criteria:
        - Step: {step_name}
        - Deliverable: {deliverable_name}
        
        {f"**Additional Context**: {additional_context}" if additional_context else ""}
        
        **INSTRUCTIONS**:
        1. Focus ONLY on the specific step and deliverable mentioned above.
        2. Ignore any content that is not relevant to the specified step and deliverable.
        3. Evaluate the submission based on the rubric criteria for the specified step.
        4. For each criterion, assign a specific score (0-10) based on the quality of the submission.
        5. In the rubric table, mark the appropriate level (Excellent/Good/Needs Improvement/Incomplete) for each criterion.
        
        **REQUIRED RESPONSE FORMAT**:
        Your evaluation MUST follow this exact format:
        
        ## Evaluation for {step_name} - {deliverable_name}
        
        ### 📋 Overview
        [Brief 2-3 sentence summary of the submission]
        
        ### 🎯 Rubric Assessment
        [Present the rubric table with specific scores and marked levels based on the submission's quality]
        
        ### 📊 Detailed Scoring
        - **Criterion 1**: [Score]/10 - [Brief justification]
        - **Criterion 2**: [Score]/10 - [Brief justification]
        - **Criterion 3**: [Score]/10 - [Brief justification]
        
        ### 📝 Detailed Evaluation
        - **Strengths**: 
          - [Specific strength 1 with reference to rubric criteria]
          - [Specific strength 2 with reference to rubric criteria]
          
        - **Areas for Improvement**:
          - [Specific area 1 with reference to rubric criteria]
          - [Specific area 2 with reference to rubric criteria]
        
        ### 🔢 Overall Score: [X]/30
        [Brief justification for the overall score based on rubric criteria]
        
        **RUBRIC FOR {step_name}**:
        
        """
        
        # Add the appropriate rubric table based on the step_name
        if "Research & Data Collection" in step_name:
            base_prompt += """
            #### Rubric: Research & Data Collection
            
            | Criteria           | Excellent (10 pts) | Good (7–9 pts) | Needs Improvement (4–6 pts) | Incomplete (0–3 pts) | Score |
            |--------------------|-------------------|----------------|----------------------------|----------------------|-------|
            | **Survey Structure** | ✅ Clear, well-organized, no bias, diverse questions | Mostly clear, some unclear wording | Basic structure, lacks variety in questions | Poorly structured, biased, or incomplete | [8]/10 |
            | **Data Collection** | 10+ valid responses collected | ✅ 7–9 responses, mostly valid | 4–6 responses, some missing data | Less than 4 responses, missing critical data | [7]/10 |
            | **Research Depth** | Uses credible sources, includes AI integration | ✅ Good sources, some AI references | Limited sources, minimal AI discussion | No sources or AI discussion included | [8]/10 |
            
            **Total Score**: [23]/30
            **Overall Rating**: [Good] (Scores: 7-9 = Good)
            """
        elif "Data Analysis & Visualization" in step_name:
            base_prompt += """
            #### Rubric: Data Analysis & Visualization
            
            | Criteria           | Excellent (10 pts) | Good (7–9 pts) | Needs Improvement (4–6 pts) | Incomplete (0–3 pts) | Score |
            |--------------------|-------------------|----------------|----------------------------|----------------------|-------|
            | **Data Organization** | ✅ Data is structured, accurate, and complete | Mostly structured, minor errors | Some organization issues, missing elements | Disorganized, missing major parts | [9]/10 |
            | **Visualization** | Graphs/charts are clear, well-labeled, insightful | ✅ Mostly clear, lacks full explanation | Basic graphs, limited insight | No graphs, unclear or missing labels | [8]/10 |
            | **Analysis Quality** | ✅ Identifies trends, includes AI insights | Identifies trends, some AI integration | Basic description, no AI insight | No analysis, data left unexplained | [9]/10 |
            
            **Total Score**: [26]/30
            **Overall Rating**: [Very Good] (Scores: 24-30 = Excellent, 18-23 = Good, 12-17 = Needs Improvement, 0-11 = Incomplete)
            """
        elif "UI Design" in step_name:
            base_prompt += """
            #### Rubric: UI/UX Design
            
            | Criteria           | Excellent (10 pts) | Good (7–9 pts) | Needs Improvement (4–6 pts) | Incomplete (0–3 pts) | Score |
            |--------------------|-------------------|----------------|----------------------------|----------------------|-------|
            | **Wireframe Design** | UI well-structured, follows best practices | ✅ Mostly clear but some UI issues | Basic layout, lacks usability | No wireframe or unclear layout | [8]/10 |
            | **User Experience** | Intuitive, easy-to-use navigation | ✅ Mostly clear, needs minor improvements | Some confusing UI elements | Poorly structured, difficult to use | [7]/10 |
            | **Usability Testing** | ✅ Feedback collected, applied improvements | Some usability feedback incorporated | Limited feedback, minimal changes | No usability test performed | [9]/10 |
            
            **Total Score**: [24]/30
            **Overall Rating**: [Good] (Scores: 24-30 = Excellent, 18-23 = Good, 12-17 = Needs Improvement, 0-11 = Incomplete)
            """
        else:
            # Default rubric for other steps
            base_prompt += """
            #### Rubric: General Assessment
            
            | Criteria           | Excellent (10 pts) | Good (7–9 pts) | Needs Improvement (4–6 pts) | Incomplete (0–3 pts) | Score |
            |--------------------|-------------------|----------------|----------------------------|----------------------|-------|
            | **Completeness** | All requirements fully addressed | ✅ Most requirements addressed | Some requirements missing | Major requirements missing | [8]/10 |
            | **Quality** | High quality work, exceeds expectations | ✅ Good quality, meets expectations | Basic quality, needs improvement | Poor quality, does not meet expectations | [8]/10 |
            | **Creativity** | Highly creative and innovative | ✅ Shows some creativity | Basic approach, lacks innovation | No evidence of creative thinking | [7]/10 |
            
            **Total Score**: [23]/30
            **Overall Rating**: [Good] (Scores: 24-30 = Excellent, 18-23 = Good, 12-17 = Needs Improvement, 0-11 = Incomplete)
            """
        
        base_prompt += """
        
        **EVALUATION INSTRUCTIONS**:
        1. Carefully review the submission against the rubric criteria for the specified step.
        2. For each criterion, select the description that best matches the submission's quality.
        3. In your evaluation, highlight the specific row in the rubric table that matches your assessment.
        4. Provide specific examples from the submission to justify your evaluation.
        5. Calculate an overall score based on the rubric criteria.
        6. Ensure your evaluation is objective, fair, and constructive.
        
        **IMPORTANT**: Only evaluate based on the specified step and deliverable. If the submission contains
        information about other steps or deliverables, ignore that content in your evaluation.
        """
        
        return base_prompt.strip()