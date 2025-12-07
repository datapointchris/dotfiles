# AWS Glue Local Development Workflow

Complete guide for developing and testing AWS Glue 5.0 jobs locally using Docker, Jupyter, Neovim, and a proper test pyramid.

## Overview

This workflow enables **100% local development** of AWS Glue jobs without AWS Glue Interactive Sessions costs, while maintaining a professional testing strategy from unit tests to end-to-end validation.

**Key Components:**

- **Jupyter in Glue Docker** - Interactive PySpark development locally
- **Neovim + Molten** - Edit notebooks in Neovim with your dotfiles
- **Three-level testing** - Unit → Integration → E2E
- **Testable code structure** - Separate business logic from Glue boilerplate

## Architecture

```bash
Development Flow:
1. Interactive development (Neovim + local Jupyter in Glue Docker)
   ↓
2. Extract functions to testable modules
   ↓
3. Unit tests (pure PySpark, no Glue - fast)
   ↓
4. Integration tests (DynamicFrame, in Glue Docker - medium)
   ↓
5. E2E tests (real AWS Glue jobs - slow but thorough)
```

## Setup

### Prerequisites

```bash
# Install Jupyter client (for kernel management)
pip install jupyter-client pynvim

# Ensure molten-nvim is installed (see Neovim config)
# Plugin file: platforms/common/.config/nvim/lua/plugins/molten.lua
```

### Project Structure

Create this structure for your Glue project:

```text
glue-project/
├── docker-compose.yml           # Glue container with Jupyter
├── Makefile                     # Helper commands
│
├── glue_jobs/                   # Job scripts
│   ├── lib/                     # Testable modules
│   │   ├── __init__.py
│   │   ├── transformations.py  # Pure transformation logic
│   │   ├── validators.py       # Data quality checks
│   │   └── utils.py            # Helper functions
│   │
│   ├── customer_etl.py         # Thin Glue job wrapper
│   └── product_etl.py
│
├── tests/
│   ├── conftest.py             # Pytest fixtures
│   ├── unit/                   # Fast unit tests (no Glue)
│   │   ├── test_transformations.py
│   │   └── test_validators.py
│   ├── integration/            # Integration tests (needs Glue Docker)
│   │   └── test_dynamicframe_ops.py
│   └── e2e/                    # E2E tests (real Glue)
│       └── test_customer_etl.py
│
├── notebooks/                  # Interactive development
│   └── customer_analysis.py   # Edit with Neovim + molten
│
├── test_data/                  # Local test data
│   ├── input/
│   └── output/
│
└── pytest.ini
```

### Docker Compose Configuration

**`docker-compose.yml`:**

```yaml
version: '3.8'

services:
  glue-jupyter:
    image: public.ecr.aws/glue/aws-glue-libs:glue_libs_5.0.0_image_01
    container_name: glue-jupyter
    ports:
      - "8888:8888"   # Jupyter
      - "4040:4040"   # Spark UI
      - "18080:18080" # Spark History Server
    volumes:
      # Project files
      - ./glue_jobs:/home/hadoop/workspace/glue_jobs
      - ./tests:/home/hadoop/workspace/tests
      - ./notebooks:/home/hadoop/workspace/notebooks
      - ./test_data:/home/hadoop/workspace/test_data

      # AWS credentials (for S3 access if needed)
      - ~/.aws:/home/hadoop/.aws:ro
    working_dir: /home/hadoop/workspace
    environment:
      - DISABLE_SSL=true
      - AWS_REGION=us-east-1
      - JUPYTER_ENABLE_LAB=yes
      - PYTHONPATH=/home/hadoop/workspace
    user: root
    command: >
      bash -c "
        pip3 install --upgrade pip &&
        pip3 install jupyter jupyterlab ipykernel pytest pytest-mock boto3 awswrangler &&

        jupyter notebook --generate-config &&

        echo \"c.NotebookApp.ip = '0.0.0.0'\" >> /root/.jupyter/jupyter_notebook_config.py &&
        echo \"c.NotebookApp.allow_root = True\" >> /root/.jupyter/jupyter_notebook_config.py &&
        echo \"c.NotebookApp.token = ''\" >> /root/.jupyter/jupyter_notebook_config.py &&
        echo \"c.NotebookApp.password = ''\" >> /root/.jupyter/jupyter_notebook_config.py &&

        echo 'Starting Jupyter Lab on http://localhost:8888' &&
        jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root
      "
```

### Makefile Helper Commands

**`Makefile`:**

```makefile
.PHONY: jupyter-start jupyter-logs jupyter-stop shell pyspark test-unit test-integration test-e2e test-all

# Start Jupyter in Glue container
jupyter-start:
 docker-compose up -d
 @echo "🚀 Jupyter running at http://localhost:8888"
 @echo "📊 Spark UI at http://localhost:4040"

# View Jupyter logs
jupyter-logs:
 docker-compose logs -f glue-jupyter

# Stop Jupyter
jupyter-stop:
 docker-compose down

# Get a shell in the container
shell:
 docker-compose exec glue-jupyter bash

# Start interactive PySpark shell
pyspark:
 docker-compose exec glue-jupyter pyspark

# Fast unit tests (no Docker needed)
test-unit:
 pytest tests/unit/ -v

# Integration tests (DynamicFrame, in Docker)
test-integration:
 docker-compose exec glue-jupyter pytest tests/integration/ -v

# E2E tests (real Glue)
test-e2e:
 pytest tests/e2e/ -v --log-cli-level=INFO

# All tests
test-all: test-unit test-integration test-e2e
```

## Code Structure

### Testable Transformation Module

**`glue_jobs/lib/transformations.py`:**

```python
"""
Transformation functions for customer data.
Functions work with both DataFrame and DynamicFrame for flexibility.
"""

from pyspark.sql import DataFrame
from awsglue.dynamicframe import DynamicFrame
from awsglue.context import GlueContext


def filter_active_customers_df(df: DataFrame) -> DataFrame:
    """
    Filter active customers (pure PySpark - easily testable).

    Args:
        df: Input DataFrame with customer data

    Returns:
        DataFrame with only active customers
    """
    return df.filter(df.status == "active")


def add_customer_tier_df(df: DataFrame) -> DataFrame:
    """
    Add customer tier based on total_spent (pure PySpark).

    Testable without Glue context!
    """
    from pyspark.sql.functions import when, col

    return df.withColumn(
        "customer_tier",
        when(col("total_spent") >= 10000, "platinum")
        .when(col("total_spent") >= 5000, "gold")
        .when(col("total_spent") >= 1000, "silver")
        .otherwise("bronze")
    )


def transform_customer_data_dyf(
    dyf: DynamicFrame,
    glue_context: GlueContext
) -> DynamicFrame:
    """
    Transform customer data using DynamicFrame (Glue-specific).

    This uses DynamicFrame but still testable in Glue Docker.
    """
    from awsglue.transforms import ApplyMapping, Filter

    # Filter using DynamicFrame
    filtered = Filter.apply(
        frame=dyf,
        f=lambda x: x["status"] == "active"
    )

    # Apply schema mapping
    mapped = ApplyMapping.apply(
        frame=filtered,
        mappings=[
            ("customer_id", "string", "customer_id", "string"),
            ("name", "string", "full_name", "string"),
            ("email", "string", "email", "string"),
            ("total_spent", "double", "total_spent", "double"),
            ("created_at", "string", "created_date", "timestamp"),
        ]
    )

    # Convert to DataFrame, add tier, convert back
    df = mapped.toDF()
    df_with_tier = add_customer_tier_df(df)

    return DynamicFrame.fromDF(df_with_tier, glue_context, "with_tier")
```

### Thin Glue Job Wrapper

**`glue_jobs/customer_etl.py`:**

```python
"""
Customer ETL Glue Job.

Thin wrapper - all logic in lib/transformations.py for testing.
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from lib.transformations import transform_customer_data_dyf


def main():
    args = getResolvedOptions(sys.argv, ['JOB_NAME'])

    sc = SparkContext()
    glueContext = GlueContext(sc)
    spark = glueContext.spark_session
    job = Job(glueContext)
    job.init(args['JOB_NAME'], args)

    # Load from Glue Catalog (not testable locally - that's OK)
    datasource = glueContext.create_dynamic_frame.from_catalog(
        database="customers_db",
        table_name="customers_raw"
    )

    # Transform (testable function!)
    transformed = transform_customer_data_dyf(datasource, glueContext)

    # Write to Glue Catalog (not testable locally - that's OK)
    glueContext.write_dynamic_frame.from_catalog(
        frame=transformed,
        database="customers_db",
        table_name="customers_processed"
    )

    job.commit()


if __name__ == "__main__":
    main()
```

## Testing Strategy

### Test Pyramid

```text
        E2E Tests (Real Glue)
        • Full job execution
        • Real S3, Glue Catalog
        • Slow (2-3 min)
        • Run before PR
       /                    \
      /  Integration Tests   \
     /   (Glue Docker)         \
    /    • DynamicFrame ops     \
   /     • GlueContext needed    \
  /      • Medium (30 sec)        \
 /       • Run frequently          \
/___________________________________\
    Unit Tests (Pure PySpark)
    • Pure transformation logic
    • No Glue dependencies
    • Fast (seconds)
    • Run on every save
```

### Level 1: Unit Tests (Pure PySpark)

**`tests/unit/test_transformations.py`:**

```python
"""
Unit tests for transformation functions.
These run FAST (no Glue Docker needed).
"""

import pytest
from pyspark.sql import Row
from glue_jobs.lib.transformations import (
    filter_active_customers_df,
    add_customer_tier_df
)


def test_filter_active_customers(spark_session):
    """Test filtering active customers (pure PySpark)"""
    # Arrange
    data = [
        Row(customer_id="1", status="active", name="Alice"),
        Row(customer_id="2", status="inactive", name="Bob"),
        Row(customer_id="3", status="active", name="Charlie"),
    ]
    df = spark_session.createDataFrame(data)

    # Act
    result = filter_active_customers_df(df)

    # Assert
    assert result.count() == 2
    names = [row.name for row in result.collect()]
    assert "Alice" in names
    assert "Charlie" in names
    assert "Bob" not in names


def test_customer_tier_assignment(spark_session):
    """Test customer tier logic (pure PySpark)"""
    data = [
        Row(customer_id="1", total_spent=15000.0),  # platinum
        Row(customer_id="2", total_spent=7000.0),   # gold
        Row(customer_id="3", total_spent=2000.0),   # silver
        Row(customer_id="4", total_spent=500.0),    # bronze
    ]
    df = spark_session.createDataFrame(data)

    result = add_customer_tier_df(df)

    tiers = {row.customer_id: row.customer_tier for row in result.collect()}
    assert tiers["1"] == "platinum"
    assert tiers["2"] == "gold"
    assert tiers["3"] == "silver"
    assert tiers["4"] == "bronze"
```

### Level 2: Integration Tests (DynamicFrame)

**`tests/integration/test_dynamicframe_ops.py`:**

```python
"""
Integration tests for DynamicFrame transformations.
These need Glue Docker (has GlueContext libraries).
"""

import pytest
from pyspark.sql import Row
from awsglue.dynamicframe import DynamicFrame
from glue_jobs.lib.transformations import transform_customer_data_dyf


def test_transform_customer_data_with_dynamicframe(spark_session, glue_context):
    """Test full transformation with DynamicFrame"""
    # Arrange
    data = [
        Row(
            customer_id="1",
            name="Alice Smith",
            email="alice@example.com",
            status="active",
            total_spent=15000.0,
            created_at="2024-01-15"
        ),
        Row(
            customer_id="2",
            name="Bob Jones",
            email="bob@example.com",
            status="inactive",
            total_spent=5000.0,
            created_at="2024-02-20"
        ),
    ]
    df = spark_session.createDataFrame(data)
    input_dyf = DynamicFrame.fromDF(df, glue_context, "test_input")

    # Act
    result_dyf = transform_customer_data_dyf(input_dyf, glue_context)

    # Assert
    result_df = result_dyf.toDF()

    # Should only have active customer
    assert result_df.count() == 1

    # Check schema mapping worked
    assert "full_name" in result_df.columns
    assert "customer_tier" in result_df.columns

    # Check tier assignment
    row = result_df.first()
    assert row.full_name == "Alice Smith"
    assert row.customer_tier == "platinum"
```

### Level 3: E2E Tests (Real Glue)

**`tests/e2e/test_customer_etl.py`:**

```python
"""
E2E tests - run real Glue job with real data.
These are VALUABLE - catch integration issues.
"""

import pytest
import boto3
import awswrangler as wr


@pytest.fixture(scope="module")
def setup_test_data():
    """Load test data into real Glue catalog tables"""
    # Load CSV to S3, create Glue table
    yield
    # Cleanup


def test_customer_etl_end_to_end(setup_test_data):
    """E2E test: Run real Glue job, verify output"""
    glue_client = boto3.client('glue')

    # Run real Glue job
    response = glue_client.start_job_run(
        JobName='customer-etl-dev',
        Arguments={'--additional-python-modules': 'custom-lib==1.0.0'}
    )

    job_run_id = response['JobRunId']

    # Wait for completion
    waiter = glue_client.get_waiter('job_run_complete')
    waiter.wait(JobName='customer-etl-dev', RunId=job_run_id)

    # Verify output using awswrangler
    df = wr.athena.read_sql_query(
        sql="SELECT * FROM customers_db.customers_processed WHERE date = CURRENT_DATE",
        database="customers_db"
    )

    # Assertions
    assert len(df) > 0, "No output data"
    assert 'customer_tier' in df.columns
    assert df['customer_tier'].isin(['platinum', 'gold', 'silver', 'bronze']).all()
```

### Pytest Configuration

**`tests/conftest.py`:**

```python
"""Pytest fixtures for all test levels"""

import pytest
from pyspark.sql import SparkSession
from awsglue.context import GlueContext


@pytest.fixture(scope="session")
def spark_session():
    """Spark session for unit tests (no Glue)"""
    spark = (
        SparkSession.builder
        .master("local[2]")
        .appName("unit-tests")
        .getOrCreate()
    )
    yield spark
    spark.stop()


@pytest.fixture(scope="session")
def glue_context(spark_session):
    """GlueContext for integration tests (needs Glue Docker)"""
    from pyspark.context import SparkContext
    sc = spark_session.sparkContext
    glue_context = GlueContext(sc)
    return glue_context
```

**`pytest.ini`:**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

## Interactive Development

### Using Neovim with Molten

**Start Jupyter in Docker:**

```bash
make jupyter-start
```

**Create notebook file** (`notebooks/customer_analysis.py`):

```python
# %% [markdown]
# # Customer Data Transformation - Local Development

# %%
# Initialize Glue context (works locally!)
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from awsglue.dynamicframe import DynamicFrame

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

print("✅ GlueContext initialized locally!")

# %%
# Create sample data
from pyspark.sql import Row

data = [
    Row(customer_id="1", name="Alice", status="active", total_spent=15000.0),
    Row(customer_id="2", name="Bob", status="inactive", total_spent=5000.0),
]

df = spark.createDataFrame(data)
dyf = DynamicFrame.fromDF(df, glueContext, "customers")

print(f"Created DynamicFrame with {dyf.count()} records")
dyf.printSchema()

# %%
# Develop transformation interactively
def transform_customer_data(input_dyf: DynamicFrame) -> DynamicFrame:
    """Transform customer data"""
    from awsglue.transforms import Filter
    from pyspark.sql.functions import when, col

    # Filter active customers
    filtered = Filter.apply(
        frame=input_dyf,
        f=lambda x: x["status"] == "active"
    )

    # Add tier
    df = filtered.toDF()
    df_with_tier = df.withColumn(
        "customer_tier",
        when(col("total_spent") >= 10000, "platinum")
        .otherwise("gold")
    )

    return DynamicFrame.fromDF(df_with_tier, glueContext, "transformed")

# Test it!
result = transform_customer_data(dyf)
result.toDF().show()
```

**In Neovim:**

```vim
" Open notebook
:e notebooks/customer_analysis.py

" Initialize Molten kernel (connects to Docker Jupyter)
<leader>mi

" Run cell under cursor
<leader>ml   " Run line
<leader>mv   " Run visual selection

" Show output
<leader>mo

" Re-run cell
<leader>mr
```

**Keybindings** (from molten.lua config):

- `<leader>mi` - Initialize kernel
- `<leader>ml` - Evaluate line
- `<leader>mv` - Evaluate visual selection
- `<leader>mr` - Re-evaluate cell
- `<leader>mo` - Show output
- `<leader>mh` - Hide output

### Alternative: Use Browser

```bash
# Open Jupyter Lab in browser
open http://localhost:8888

# Create notebook, develop interactively
# Full Glue libraries available!
```

## Complete Development Cycle

### Daily Workflow

```bash
# 1. Start Jupyter in Glue container
make jupyter-start

# 2. Interactive development in Neovim
nvim notebooks/customer_transform.py
# <leader>mi to initialize kernel
# Develop and test function interactively

# 3. Extract working function to module
# notebooks/customer_transform.py → glue_jobs/lib/transformations.py

# 4. Write unit tests (fast feedback)
nvim tests/unit/test_transformations.py
make test-unit  # Runs in seconds

# 5. Write integration tests
nvim tests/integration/test_dynamicframe_ops.py
make test-integration  # Runs in Docker

# 6. Update Glue job script
nvim glue_jobs/customer_etl.py

# 7. Final E2E validation
make test-e2e  # Runs real Glue job

# 8. Stop container
make jupyter-stop
```

### Development to Production Path

```text
1. Interactive dev (Neovim + local Jupyter)
   • Rapid iteration
   • Immediate feedback
   • Full Glue libraries
   ↓
2. Extract to modules (glue_jobs/lib/)
   • Testable functions
   • Reusable logic
   ↓
3. Unit tests (seconds)
   • Pure PySpark
   • No Glue dependencies
   ↓
4. Integration tests (30 sec)
   • DynamicFrame operations
   • Glue Docker environment
   ↓
5. E2E tests (2-3 min)
   • Real Glue job execution
   • Full validation
   ↓
6. Production deployment
   • Tested and validated
   • Confident deployment
```

## Troubleshooting

### Jupyter Won't Start

```bash
# Check logs
make jupyter-logs

# Verify container is running
docker ps | grep glue-jupyter

# Restart container
make jupyter-stop
make jupyter-start
```

### Can't Connect from Neovim

```bash
# Verify Jupyter is accessible
curl http://localhost:8888

# Check available kernels
jupyter kernelspec list

# Verify kernel in Docker
docker-compose exec glue-jupyter jupyter kernelspec list
```

### GlueContext Not Found

Make sure you're running code in the Docker container (via Molten connection to local Jupyter kernel, not a separate Python interpreter).

### Import Errors in Tests

```bash
# Set PYTHONPATH in docker-compose.yml
environment:
  - PYTHONPATH=/home/hadoop/workspace

# Or in pytest
export PYTHONPATH=$PWD
pytest tests/unit/
```

## Key Advantages

✅ **100% Local** - No AWS Glue Interactive Session costs
✅ **Full Glue Libraries** - GlueContext, DynamicFrame, everything works
✅ **Neovim Workflow** - Edit with your dotfiles
✅ **Fast Iteration** - No network latency
✅ **Real S3 Testing** - Mount AWS credentials for dev S3 buckets
✅ **Proper Test Pyramid** - Unit → Integration → E2E
✅ **Production Parity** - Glue 5.0 Docker = production Glue 5.0

## References

- [AWS Glue 5.0 local development](https://aws.amazon.com/blogs/big-data/develop-and-test-aws-glue-5-0-jobs-locally-using-a-docker-container/)
- [AWS Glue local testing documentation](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html)
- [Pytest for AWS Glue jobs](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/run-unit-tests-for-python-etl-jobs-in-aws-glue-using-the-pytest-framework.html)
- [Molten-nvim Jupyter plugin](https://github.com/benlubas/molten-nvim)
- [Running Jupyter in Glue Docker](https://github.com/purecloudlabs/aws_glue_etl_docker)
