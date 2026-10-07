import argparse
import json

from videoagents.contracts import Brief
from videoagents.default_config import RUNTIME_ROOT
from videoagents.storage import Repository


def main():
    parser = argparse.ArgumentParser(description="VideoAgents task CLI (same durable API services)")
    parser.add_argument("--topic", default="")
    parser.add_argument("--direction", default="", help="本期创作方向，不需要写成口播稿")
    parser.add_argument("--script", default="")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    repository = Repository(RUNTIME_ROOT)
    if args.list:
        print(json.dumps([job.model_dump() for job in repository.list_jobs()], ensure_ascii=False, indent=2))
    else:
        print(repository.create_job(Brief(topic=args.topic, creative_direction=args.direction,
                                         script_text=args.script)).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
