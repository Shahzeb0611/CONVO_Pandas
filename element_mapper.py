# processors/element_mapper.py
# I'll be adding this new line to show that the file has been changed
import json
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from src.core.base_processor import BaseProcessor
from src.core.exceptions import ProcessingError
from src.utils.file_utils import ensure_directory

class ElementMapper(BaseProcessor):
    """Map test case actions to webpage elements using Selenium"""
    
    def __init__(self, headless=True):
        super().__init__()
        self.headless = headless
        self.driver = None
        self.wait = None
        self.element_selectors = []
        
    def setup_driver(self):
        """Initialize Selenium WebDriver"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.logger.info("WebDriver initialized successfully")
    
    def cleanup_driver(self):
        """Clean up WebDriver resources"""
        if self.driver:
            self.driver.quit()
            self.logger.info("WebDriver closed")
    
    def find_elements_by_action_type(self, action_type: str, element_description: str) -> List[Dict]:
        """Find relevant elements based on action type and description"""
        elements = []
        
        try:
            if action_type == "Navigate":
                # For navigation, capture page title and URL
                elements.append({
                    "element_type": "page",
                    "selector": "title",
                    "selector_type": "tag",
                    "text_content": self.driver.title,
                    "attributes": {"url": self.driver.current_url}
                })
                
            elif action_type == "Click":
                # Find clickable elements (buttons, links, etc.)
                clickable_selectors = [
                    "//button", "//a", "//input[@type='submit']", 
                    "//input[@type='button']", "//div[@role='button']",
                    "//span[@role='button']"
                ]
                
                for selector in clickable_selectors:
                    try:
                        web_elements = self.driver.find_elements(By.XPATH, selector)
                        for elem in web_elements:
                            if elem.is_displayed() and elem.is_enabled():
                                element_info = self.extract_element_info(elem, selector)
                                if self.is_relevant_element(element_info, element_description):
                                    elements.append(element_info)
                    except Exception as e:
                        continue
                        
            elif action_type == "Input Text":
                # Find input fields
                input_selectors = [
                    "//input[@type='text']", "//input[@type='email']",
                    "//input[@type='password']", "//textarea", "//input[not(@type)]"
                ]
                
                for selector in input_selectors:
                    try:
                        web_elements = self.driver.find_elements(By.XPATH, selector)
                        for elem in web_elements:
                            if elem.is_displayed() and elem.is_enabled():
                                element_info = self.extract_element_info(elem, selector)
                                if self.is_relevant_element(element_info, element_description):
                                    elements.append(element_info)
                    except Exception as e:
                        continue
                        
            elif action_type == "Select":
                # Find select dropdowns
                select_elements = self.driver.find_elements(By.TAG_NAME, "select")
                for elem in select_elements:
                    if elem.is_displayed() and elem.is_enabled():
                        element_info = self.extract_element_info(elem, "//select")
                        if self.is_relevant_element(element_info, element_description):
                            elements.append(element_info)
                            
            elif action_type in ["Verify", "Assert"]:
                # Find elements for verification
                verify_selectors = ["//div", "//span", "//p", "//h1", "//h2", "//h3"]
                for selector in verify_selectors:
                    try:
                        web_elements = self.driver.find_elements(By.XPATH, selector)
                        for elem in web_elements[:5]:  # Limit to first 5 to avoid too many elements
                            if elem.is_displayed() and elem.text:
                                element_info = self.extract_element_info(elem, selector)
                                if self.is_relevant_element(element_info, element_description):
                                    elements.append(element_info)
                    except Exception as e:
                        continue
                        
        except Exception as e:
            self.logger.error(f"Error finding elements for action {action_type}: {e}")
            
        return elements
    
    def extract_element_info(self, element, xpath_selector: str) -> Dict:
        """Extract comprehensive information about a web element"""
        element_info = {
            "element_type": element.tag_name,
            "selector": xpath_selector,
            "selector_type": "xpath",
            "text_content": element.text.strip() if element.text else "",
            "attributes": {}
        }
        
        # Extract common attributes
        common_attrs = ["id", "name", "class", "type", "placeholder", "value", "href", "title"]
        for attr in common_attrs:
            try:
                attr_value = element.get_attribute(attr)
                if attr_value:
                    element_info["attributes"][attr] = attr_value
            except Exception:
                continue
                
        # Generate alternative selectors
        element_info["alternative_selectors"] = self.generate_alternative_selectors(element_info)
        
        return element_info
    
    def generate_alternative_selectors(self, element_info: Dict) -> List[Dict]:
        """Generate multiple selector options for an element"""
        selectors = []
        attrs = element_info["attributes"]
        
        # ID selector (highest priority)
        if "id" in attrs:
            selectors.append({
                "type": "id",
                "selector": attrs["id"],
                "priority": 1
            })
            
        # Name selector
        if "name" in attrs:
            selectors.append({
                "type": "name", 
                "selector": attrs["name"],
                "priority": 2
            })
            
        # Class selector
        if "class" in attrs:
            selectors.append({
                "type": "class",
                "selector": attrs["class"],
                "priority": 3
            })
            
        # Text content selector
        if element_info["text_content"]:
            selectors.append({
                "type": "text",
                "selector": element_info["text_content"],
                "priority": 4
            })
            
        return selectors
    
    def is_relevant_element(self, element_info: Dict, description: str) -> bool:
        """Determine if element is relevant to the action description"""
        description_lower = description.lower()
        
        # Check text content
        if element_info["text_content"]:
            if any(word in element_info["text_content"].lower() for word in description_lower.split()):
                return True
                
        # Check attributes
        for attr_value in element_info["attributes"].values():
            if isinstance(attr_value, str):
                if any(word in attr_value.lower() for word in description_lower.split()):
                    return True
                    
        # Default relevance for common elements
        common_elements = ["button", "input", "select", "a"]
        return element_info["element_type"] in common_elements
    
    def map_test_case_elements(self, test_case: Dict, url_mappings: Dict) -> Dict:
        """Map elements for a single test case"""
        test_id = test_case["test_id"]
        self.logger.info(f"Mapping elements for test case: {test_id}")
        
        mapped_elements = {
            "test_id": test_id,
            "test_name": test_case["test_name"],
            "description": test_case["description"],
            "step_elements": []
        }
        
        # Get URL mappings for this test case
        test_mappings = url_mappings["test_mappings"].get(test_id, {})
        
        for step in test_case["test_steps"]:
            step_number = step["step_number"]
            step_elements = {
                "step_number": step_number,
                "original_action_description": step["original_action_description"],
                "pom_action_elements": []
            }
            
            # Find step mapping in URL mappings
            step_mapping = None
            if "ai_analysis" in test_mappings:
                for mapping in test_mappings["ai_analysis"]["mappings"]:
                    if mapping["step_number"] == step_number:
                        step_mapping = mapping
                        break
            
            for pom_action in step["pom_actions"]:
                action_elements = {
                    "sub_step_number": pom_action["sub_step_number"],
                    "action_type": pom_action["action_type"],
                    "element": pom_action["element"],
                    "action_detail": pom_action["action_detail"],
                    "target_url": None,
                    "discovered_elements": []
                }
                
                # Get URL for this action
                if step_mapping:
                    for sub_step in step_mapping["step_mappings"]:
                        if sub_step["sub_step_number"] == pom_action["sub_step_number"]:
                            if sub_step["recommended_urls"]:
                                action_elements["target_url"] = sub_step["recommended_urls"][0]["url"]
                            break
                
                # Navigate to URL and find elements
                if action_elements["target_url"]:
                    try:
                        self.driver.get(action_elements["target_url"])
                        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                        
                        # Find elements for this action
                        elements = self.find_elements_by_action_type(
                            pom_action["action_type"],
                            pom_action["element"]
                        )
                        action_elements["discovered_elements"] = elements
                        
                    except Exception as e:
                        self.logger.error(f"Error processing URL {action_elements['target_url']}: {e}")
                        action_elements["error"] = str(e)
                
                step_elements["pom_action_elements"].append(action_elements)
            
            mapped_elements["step_elements"].append(step_elements)
        
        return mapped_elements
    
    def process(self, actions_file: str, url_mappings_file: str, output_dir: str = None) -> Dict[str, Any]:
        """Main processing method to map all test case elements"""
        self.logger.info("Starting element mapping process")
        
        if output_dir is None:
            output_dir = self.config.OUTPUT_DIR
        else:
            output_dir = Path(output_dir)
            
        ensure_directory(output_dir)
        
        try:
            # Load input files
            with open(actions_file, 'r') as f:
                actions_data = json.load(f)
                
            with open(url_mappings_file, 'r') as f:
                url_mappings = json.load(f)
            
            # Setup Selenium driver
            self.setup_driver()
            
            # Process each test case
            all_mapped_elements = []
            
            for test_case in actions_data["test_cases"]:
                mapped_elements = self.map_test_case_elements(test_case, url_mappings)
                all_mapped_elements.append(mapped_elements)
            
            # Create output structure
            output_data = {
                "mapping_metadata": {
                    "processing_timestamp": datetime.datetime.now().isoformat(),
                    "source_actions_file": actions_file,
                    "source_url_mappings_file": url_mappings_file,
                    "total_test_cases_mapped": len(all_mapped_elements),
                    "selenium_driver": "Chrome",
                    "headless_mode": self.headless
                },
                "element_mappings": all_mapped_elements
            }
            
            # Save output
            output_file = self.save_json(output_data, "element_mappings.json", output_dir)
            
            self.logger.info(f"Element mapping completed successfully!")
            self.logger.info(f"Output saved to: {output_file}")
            
            return {
                "success": True,
                "output_file": str(output_file),
                "total_test_cases_mapped": len(all_mapped_elements),
                "processing_timestamp": datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Element mapping failed: {e}"
            self.logger.error(error_msg)
            return {"error": error_msg}
            
        finally:
            self.cleanup_driver()