python_sources(
    name="onboarding_mascot", sources=["**/*.py"], dependencies=["//:env_file"]
)

python_tests(
    name="tests",
    sources=["tests/**/test_*.py"],
    dependencies=[":tests_support_files", "//:env_file"],
    tags=["unit"],
)

resources(
    name="tests_support_files",
    sources=["tests/**/*"],
)

python_aws_lambda_function(
    name="lambda",
    handler="app.py:lambda_handler",
    complete_platforms=["3rdparty/platforms:aws_lambda_python_3_10"],
)
