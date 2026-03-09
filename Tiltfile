compose_file = "deploy/compose/docker-compose.dev.yml"
docker_compose(compose_file)

# Infrastructure
dc_resource("db", labels=["infra"])
dc_resource("mq", labels=["infra"])
dc_resource("redis", labels=["infra"])

# Core app services
dc_resource("api-go", labels=["apps"], resource_deps=["db"])
dc_resource("workers-py", labels=["apps"], resource_deps=["db", "mq"])

# SaaS demo services
dc_resource("saas-api", labels=["saas"], resource_deps=["redis"])
dc_resource("saas-rq-worker", labels=["saas"], resource_deps=["redis"])

# Automation / orchestration
dc_resource("n8n", labels=["automation"], resource_deps=["db", "mq"])
