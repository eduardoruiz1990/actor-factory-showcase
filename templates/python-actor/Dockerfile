# Based on Apify's official python-start template. Python 3.12 matches the factory's CI.
FROM apify/actor-python:3.12

# Copy only requirements.txt first, so the dependency layer is cached between builds.
COPY --chown=myuser:myuser requirements.txt ./

RUN echo "Python version:" \
 && python --version \
 && echo "Pip version:" \
 && pip --version \
 && echo "Installing dependencies:" \
 && pip install -r requirements.txt \
 && echo "All installed Python packages:" \
 && pip freeze

# Then the source code; tests are excluded by .dockerignore.
COPY --chown=myuser:myuser . ./

# Fail the build early if the code does not compile.
RUN python -m compileall -q my_actor/

CMD ["python", "-m", "my_actor"]
