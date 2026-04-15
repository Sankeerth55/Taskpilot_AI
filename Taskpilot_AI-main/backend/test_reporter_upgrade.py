"""
Test script for upgraded ReporterAgent with BART model.

Tests all output formats:
- 5-line summaries
- Point-wise answers  
- Bullet lists
- Structured explanations
- Normal summaries
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.agents.reporter import ReporterAgent
from app.services.agents.base import AgentContext
from app.services.ai.factory import get_provider


async def test_reporter_formats():
    """Test ReporterAgent with different output formats."""
    
    print("=" * 80)
    print("TESTING UPGRADED REPORTERAGENT WITH BART MODEL")
    print("=" * 80)
    
    # Initialize ReporterAgent
    llm = get_provider()
    reporter = ReporterAgent(llm)
    
    # Check if BART model loaded
    if reporter._bart_pipeline:
        print("✓ BART model loaded successfully!")
    else:
        print("⚠ BART model not loaded - will use fallback")
    
    print()
    
    # Test cases with different formats
    test_cases = [
        {
            "name": "5-Line Summary",
            "user_input": "Give me a 5 line summary about artificial intelligence",
            "context": """
            Artificial intelligence (AI) is intelligence demonstrated by machines, in contrast to the natural intelligence displayed by humans. 
            AI research has been defined as the field of study of intelligent agents, which refers to any system that perceives its environment and 
            takes actions that maximize its chance of achieving its goals. The term "artificial intelligence" had previously been used to describe 
            machines that mimic and display "human" cognitive skills that are associated with the human mind, such as "learning" and "problem-solving". 
            This definition has been rejected by major AI researchers who now describe AI in terms of rationality and acting rationally, which does 
            not limit how intelligence can be articulated. AI applications include advanced web search engines, recommendation systems, 
            understanding human speech, self-driving cars, automated decision-making and competing at the highest level in strategic game systems.
            """,
            "intent": "explain"
        },
        {
            "name": "Point-wise Answer",
            "user_input": "What are the key features of machine learning in points?",
            "context": """
            Machine learning is a method of data analysis that automates analytical model building. It is a branch of artificial intelligence 
            based on the idea that systems can learn from data, identify patterns and make decisions with minimal human intervention. 
            Key features include: pattern recognition from large datasets, ability to improve automatically through experience, 
            handling of complex and high-dimensional data, making predictions based on historical data, and adaptation to new scenarios without 
            explicit programming. Machine learning algorithms are used in a wide variety of applications, including email filtering and 
            computer vision, where it is difficult to develop conventional algorithms.
            """,
            "intent": "explain"
        },
        {
            "name": "Bullet List",
            "user_input": "List the benefits of cloud computing",
            "context": """
            Cloud computing offers numerous benefits to businesses and individuals. Cost efficiency is achieved through reduced infrastructure 
            and operational costs. Scalability allows resources to be easily scaled up or down based on demand. Accessibility enables access 
            to data and applications from anywhere with internet connectivity. Disaster recovery is simplified with automatic backup and 
            recovery solutions. Collaboration is enhanced as team members can work together on documents and projects in real-time. 
            Security is often better than traditional on-premise solutions with professional security teams managing the infrastructure. 
            Automatic software updates ensure systems are always up-to-date without manual intervention.
            """,
            "intent": "research"
        },
        {
            "name": "Structured Explanation",
            "user_input": "Explain how neural networks work",
            "context": """
            Neural networks are computing systems inspired by the biological neural networks that constitute animal brains. 
            They consist of interconnected nodes called neurons organized in layers. The input layer receives data, hidden layers 
            process information through weighted connections, and the output layer produces results. Each connection has a weight 
            that adjusts as learning proceeds. The network learns by adjusting these weights through a process called backpropagation, 
            which minimizes the difference between predicted and actual outputs. Activation functions introduce non-linearity, 
            allowing the network to learn complex patterns. Deep learning uses multiple hidden layers to extract progressively 
            higher-level features from raw input.
            """,
            "intent": "explain"
        },
        {
            "name": "Normal Summary",
            "user_input": "Summarize the history of the internet",
            "context": """
            The Internet began as ARPANET in the late 1960s, a project funded by the U.S. Department of Defense. 
            It was designed to enable computers at different universities and research institutions to communicate. 
            TCP/IP protocols were developed in the 1970s, forming the backbone of modern internet communication. 
            The World Wide Web was invented by Tim Berners-Lee in 1989 at CERN, revolutionizing how information was shared. 
            The 1990s saw the commercialization of the internet and the dot-com boom. Search engines like Google emerged 
            in the late 1990s, making information more accessible. Social media platforms began appearing in the 2000s, 
            transforming how people connect and share information. Today, the internet is essential infrastructure supporting 
            billions of users worldwide, enabling e-commerce, remote work, entertainment, and countless other applications.
            """,
            "intent": "research"
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}: {test_case['name']}")
        print(f"{'=' * 80}")
        print(f"Query: {test_case['user_input']}")
        print(f"\nExpected Format: {test_case['name']}")
        print(f"\n{'-' * 80}")
        
        # Create context
        context = AgentContext(
            user_input=test_case['user_input'],
            fetched_context=test_case['context']
        )
        context.metadata["intent"] = test_case['intent']
        
        # Run reporter
        try:
            result = await reporter.run(context)
            
            print(f"Status: {result.status}")
            print(f"Method: {result.details.get('method', 'unknown')}")
            print(f"Format: {result.details.get('format', 'unknown')}")
            print(f"\nGenerated Response:")
            print(f"{'-' * 80}")
            print(result.output)
            print(f"{'-' * 80}")
            
            # Validation
            if result.status == "complete" and result.output:
                print("✓ Response generated successfully")
            else:
                print("✗ Response generation failed")
                
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'=' * 80}")
    print("ALL TESTS COMPLETED")
    print(f"{'=' * 80}\n")


async def test_file_handling():
    """Test ReporterAgent with file content (PDF, DOC, etc.)."""
    
    print("\n" + "=" * 80)
    print("TESTING FILE CONTENT SUMMARIZATION")
    print("=" * 80)
    
    llm = get_provider()
    reporter = ReporterAgent(llm)
    
    # Simulate PDF content
    test_case = {
        "name": "PDF Summary",
        "user_input": "Summarize this document",
        "context": """
        📎 UPLOADED FILES:
        
        Document: research_paper.pdf
        
        Abstract: This paper presents a comprehensive study on renewable energy sources and their impact on climate change mitigation.
        Solar and wind energy have shown remarkable growth over the past decade, with installation costs decreasing by 80% for solar 
        and 50% for wind power. The study analyzes data from 50 countries and demonstrates that renewable energy adoption has led to 
        a 15% reduction in carbon emissions in countries with aggressive renewable energy policies. Battery storage technology has 
        improved significantly, addressing the intermittency issues of renewable sources. Economic analysis shows that renewable 
        energy is now cost-competitive with fossil fuels in many markets. The paper concludes that accelerated adoption of renewable 
        energy, combined with energy efficiency measures and carbon pricing, could limit global warming to 1.5°C by 2050.
        """,
        "intent": "analyze_file"
    }
    
    print(f"Query: {test_case['user_input']}")
    print(f"File Type: PDF")
    print(f"\n{'-' * 80}")
    
    context = AgentContext(
        user_input=test_case['user_input'],
        fetched_context=test_case['context']
    )
    context.metadata["intent"] = test_case['intent']
    
    try:
        result = await reporter.run(context)
        
        print(f"Status: {result.status}")
        print(f"Method: {result.details.get('method', 'unknown')}")
        print(f"\nGenerated Summary:")
        print(f"{'-' * 80}")
        print(result.output)
        print(f"{'-' * 80}")
        
        if result.status == "complete" and result.output:
            print("✓ PDF content summarized successfully")
        else:
            print("✗ PDF summarization failed")
            
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    print("\n🚀 Starting ReporterAgent Upgrade Tests\n")
    
    # Run format tests
    asyncio.run(test_reporter_formats())
    
    # Run file handling test
    asyncio.run(test_file_handling())
    
    print("\n✅ All tests completed!\n")
