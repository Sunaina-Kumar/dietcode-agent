import asyncio
import sys
from agent.orchestrator import DietCodeAgent


async def main():
    """Main CLI entry point"""
    if len(sys.argv) < 4:
        print("Usage: python -m src.main <owner> <repo> <pr_number>")
        print("Example: python -m src.main octocat Hello-World 123")
        sys.exit(1)
    
    owner = sys.argv[1]
    repo = sys.argv[2]
    pr_number = int(sys.argv[3])
    
    agent = DietCodeAgent()
    
    try:
        result = await agent.process_pr_failure(owner, repo, pr_number)
        
        print("\n" + "="*50)
        print("RESULT:")
        print("="*50)
        
        import json
        print(json.dumps(result, indent=2, default=str))
        
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())