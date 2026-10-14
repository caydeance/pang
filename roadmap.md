Day 1 — Polish the core
- Add AI opponent (track ball with limited speed/max speed cap)
- Ball speed ramps up per rally; cap max speed
- Sound effects (paddle hit, wall, score) via ebiten/audio
- Pause (Space) + restart (R) states
Day 2 — Game flow
- Start menu → play → game-over (first to 7/11)
- Game state machine (Menu, Playing, Paused, GameOver)
- Font rendering for scores/titles (ebiten/text instead of DebugPrint)
- Fixed timestep so physics aren't FPS-dependent (ebiten.SetTPS)
Day 3 — Feel & juice
- Screen shake on hits, ball trail
- Particle burst on score
- Smooth paddle accel instead of instant movement
- Difficulty settings (easy/med/hard AI)
Day 4 — Ship it
- Refactor into files (game.go, ai.go, audio.go, menu.go)
- Cross-compile: GOOS=windows go build, GOOS=js GOARCH=wasm for web
- Add README.md with controls + build instructions
- Final playtest, tag v1.0

ai roadmap
