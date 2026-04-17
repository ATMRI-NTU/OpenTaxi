# Changelog

All notable changes to OpenTaxi are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-17

### Added
- **Official PyPI release** with Trusted Publishing setup
- GitHub Organization (`ATMRI-NTU`) for professional project management
- GitHub Actions CI/CD workflow for automated PyPI publishing
- Comprehensive documentation (CONTRIBUTING.md, CHANGELOG.md, improved README)
- Author attribution and citation information in package metadata
- Optional dependencies configuration (RL, visualization)

### Changed
- Updated GitHub URLs to point to `ATMRI-NTU/OpenTaxi` organization
- Improved README with PyPI installation instructions and full author list
- Enhanced project metadata with actual author names and emails

### Fixed
- GitHub Actions workflow authentication for private repository access
- Deprecated Node.js 20 actions updated to latest versions

## [0.1.0] - 2026-04-12

### Initial Release (TestPyPI)

#### Added
- **Graph-based Airport Simulator**: Core simulation engine for airport surface operations
  - Multi-aircraft modeling with kinematic dynamics
  - Arc-length parameterization for trajectory tracking
  - Realistic acceleration/deceleration limits

- **Path Planning Algorithms**:
  - A* with optional turn penalty
  - Dijkstra's algorithm
  - Greedy search
  - Floyd-Warshall (precomputed all-pairs)

- **Conflict Detection & Resolution**:
  - Prediction-based First-Come-First-Served (FCFS) controller
  - Separation-maximizing (Opt_StopGo) controller
  - Configurable separation thresholds

- **Evaluation Framework**:
  - Path quality metrics (length, turn angle, turn count, smoothness)
  - Simulation metrics (conflict count, taxi time, throughput)
  - CSV export of results

- **Reinforcement Learning Integration**:
  - Gymnasium-compatible environment (`AirportRLEnv`)
  - Stable-baselines3 integration for policy training
  - Binary action space (Go/Stop) for aircraft control

- **Real-time Visualization**:
  - Matplotlib-based 2D taxiway network rendering
  - Aircraft position and heading visualization
  - Trajectory trails with history
  - Risk level coloring (separation-based)

- **Data Support**:
  - GraphML airport map parsing
  - UTM coordinate projection
  - Historical trajectory replay capability
  - Synthetic traffic scenario generation

- **Case Studies**:
  - Taxi routing benchmark on Changi Airport (Table 1)
  - Conflict resolution comparison (Figure 3)
  - PPO reinforcement learning example (Figure 4)
  - Multi-airport generalization demo (Doha, Hong Kong)

#### Validated
- Kinematic model calibration against real Changi Airport data
- Runway occupancy time (ROT) distribution matching via Gaussian Mixture Models
- Aircraft taxi-out time distributions (paired t-test, p-value = 0.793)

#### Dependencies
- **Core**: numpy, networkx, pyproj, matplotlib
- **Visualization**: cairosvg, Pillow, contextily (optional)
- **RL**: gymnasium, stable-baselines3, scipy (optional)

---

## Feature Roadmap

### Under Consideration
- [ ] Automated OSM to GraphML conversion pipeline
- [ ] Extended multi-airport support (additional airport maps)
- [ ] Ground vehicle integration
- [ ] Advanced RL state/action formulations
- [ ] Performance benchmarking suite
- [ ] Comprehensive unit and integration tests
- [ ] Jupyter notebook tutorials
- [ ] RESTful API for simulation access
- [ ] Web-based visualization interface

---

## Version History Summary

| Version | Release Date | PyPI | Status |
|---------|--------------|------|--------|
| 0.2.0   | 2026-04-17   | ✅ Official | Stable |
| 0.1.0   | 2026-04-12   | ⚠️ TestPyPI | Pre-release |

---

## How to Report Issues

Please report bugs or suggest features on the [OpenTaxi GitHub Issues](https://github.com/ATMRI-NTU/OpenTaxi/issues) page.

## License

OpenTaxi is released under the MIT License. See [LICENSE](LICENSE) for details.

## Citation

If you use OpenTaxi in your research, please cite:

```bibtex
@software{opentaxi2025,
  title  = {OpenTaxi: Open-Source Modular Simulator for Airport Surface Operations},
  author = {Ali, Hasnain and Yang, Haohan and Pham, Duc-Thinh and Alam, Sameer},
  year   = {2025},
  url    = {https://github.com/ATMRI-NTU/OpenTaxi}
}
```
