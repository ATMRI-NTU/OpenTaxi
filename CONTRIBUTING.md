# Contributing to OpenTaxi

Thank you for your interest in contributing to OpenTaxi! We welcome contributions in the form of bug reports, feature requests, code improvements, documentation enhancements, and research applications.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and professional in all interactions.

## How to Contribute

### Reporting Issues

If you find a bug or have a feature request, please open an issue on GitHub:

1. Go to [OpenTaxi Issues](https://github.com/ATMRI-NTU/OpenTaxi/issues)
2. Click **"New Issue"**
3. Provide a clear title and detailed description
4. Include steps to reproduce (for bugs) or use cases (for features)
5. Attach relevant code, error messages, or screenshots

### Contributing Code

1. **Fork the repository** at https://github.com/ATMRI-NTU/OpenTaxi

2. **Clone your fork locally**
   ```bash
   git clone https://github.com/YOUR-USERNAME/OpenTaxi.git
   cd OpenTaxi
   ```

3. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Make your changes**
   - Follow PEP 8 style guidelines for Python code
   - Add docstrings to functions and classes
   - Include comments for complex logic
   - Update relevant documentation

5. **Install development dependencies**
   ```bash
   pip install -e ".[full]"
   ```

6. **Test your changes**
   - Run existing examples: `python examples/run_sim.py`
   - Consider adding unit tests for new functionality

7. **Commit and push**
   ```bash
   git add .
   git commit -m "Clear description of your changes"
   git push origin feature/your-feature-name
   ```

8. **Open a Pull Request**
   - Go to https://github.com/ATMRI-NTU/OpenTaxi/pulls
   - Click **"New Pull Request"**
   - Describe what your changes do and why they're needed
   - Link any related issues

### Pull Request Guidelines

- Keep PRs focused on a single feature or fix
- Update documentation if your changes affect user-facing APIs
- Include examples for new features
- Ensure code is compatible with Python 3.8+
- Reference any related issues in the PR description

## Development Setup

### Environment Setup

```bash
git clone https://github.com/ATMRI-NTU/OpenTaxi.git
cd OpenTaxi

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[full]"
```

### Running Examples

```bash
# Basic simulation
python examples/run_sim.py --agents 10 --max-steps 5000

# RL training
python examples/train_rl.py train --output-dir ./logs
```

## Project Structure

- `opentaxi/` – Core package modules
  - `airport.py` – Airport map loading and parsing
  - `aircraft.py` – Aircraft kinematic model
  - `planners.py` – Path planning algorithms
  - `controller.py` – Conflict detection and resolution
  - `simulator.py` – Main simulation engine
  - `evaluation.py` – Performance metrics
  - `rl_env.py` – Gymnasium RL environment
  - `tools.py` – Utility functions
- `examples/` – Example scripts
- `docs/` – Documentation

## Areas for Contribution

We're particularly interested in contributions in these areas:

1. **New Path Planning Algorithms** – Implement novel routing strategies
2. **Advanced Conflict Resolution** – Develop new tactical approaches
3. **Multi-Airport Support** – Add new airport maps in GraphML format
4. **RL Extensions** – New state/action space formulations, reward functions
5. **Documentation** – Improve guides, tutorials, API documentation
6. **Testing** – Add unit and integration tests
7. **Performance Optimization** – Improve scalability and speed
8. **Visualization Enhancements** – Improve real-time graphics and analysis tools

## Citation

If your contribution leads to a publication, please cite OpenTaxi:

```bibtex
@software{opentaxi2025,
  title  = {OpenTaxi: Open-Source Modular Simulator for Airport Surface Operations},
  author = {Ali, Hasnain and Yang, Haohan and Pham, Duc-Thinh and Alam, Sameer},
  year   = {2025},
  url    = {https://github.com/ATMRI-NTU/OpenTaxi}
}
```

## Questions?

For questions about contributing, feel free to:
- Open an issue with the `[question]` label
- Contact the maintainers at sameeralam@ntu.edu.sg

Thank you for contributing to OpenTaxi! 🎉
