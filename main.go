package main

import (
	"image/color"
	"log"
	"math"
	"math/rand"
	"strconv"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/audio"
	"github.com/hajimehoshi/ebiten/v2/ebitenutil"
	"github.com/hajimehoshi/ebiten/v2/inpututil"
)

const (
	screenWidth  = 640
	screenHeight = 480

	paddleW = 12
	paddleH = 80
	paddleX = 24

	paddleSpeed = 360.0
	aiSpeed     = 300.0

	ballSize     = 12
	ballSpeed    = 300.0
	maxBallSpeed = 640.0
	ballSpeedUp  = 1.06
	maxBounceAng = math.Pi / 3
	sampleRate   = 48000
)

var audioCtx *audio.Context

var (
	white = color.RGBA{0xff, 0xff, 0xff, 0xff}
)

type colorRect struct {
	x, y, w, h float64
	clr        color.Color
}

func (r *colorRect) Draw(screen *ebiten.Image) {
	ebitenutil.DrawRect(screen, r.x, r.y, r.w, r.h, r.clr)
}

func (r *colorRect) overlaps(o *colorRect) bool {
	return r.x < o.x+o.w && r.x+r.w > o.x &&
		r.y < o.y+o.h && r.y+r.h > o.y
}

type Game struct {
	leftPaddle  colorRect
	rightPaddle colorRect
	ball        colorRect

	ballVX float64
	ballVY float64
	speed  float64

	leftScore  int
	rightScore int

	vsAI   bool
	paused bool

	sPaddle *audio.Player
	sWall   *audio.Player
	sScore  *audio.Player
}

func NewGame() *Game {
	g := &Game{
		leftPaddle:  colorRect{x: paddleX, y: screenHeight/2 - paddleH/2, w: paddleW, h: paddleH, clr: white},
		rightPaddle: colorRect{x: screenWidth - paddleX - paddleW, y: screenHeight/2 - paddleH/2, w: paddleW, h: paddleH, clr: white},
		ball:        colorRect{x: screenWidth/2 - ballSize/2, y: screenHeight/2 - ballSize/2, w: ballSize, h: ballSize, clr: white},
		vsAI:        true,
	}
	if audioCtx != nil {
		g.sPaddle = audio.NewPlayerFromBytes(audioCtx, tone(440, 0.06, 0.5))
		g.sWall = audio.NewPlayerFromBytes(audioCtx, tone(220, 0.05, 0.4))
		g.sScore = audio.NewPlayerFromBytes(audioCtx, tone(660, 0.18, 0.5))
	}
	g.resetBall(1)
	return g
}

func (g *Game) play(p *audio.Player) {
	if p == nil {
		return
	}
	_ = p.Rewind()
	p.Play()
}

func tone(freq, secs, vol float64) []byte {
	n := int(secs * sampleRate)
	buf := make([]byte, n*4)
	for i := 0; i < n; i++ {
		t := float64(i) / sampleRate
		env := math.Exp(-4 * t / secs)
		s := int16(math.Sin(2*math.Pi*freq*t) * env * vol * math.MaxInt16)
		buf[i*4] = byte(s)
		buf[i*4+1] = byte(s >> 8)
		buf[i*4+2] = byte(s)
		buf[i*4+3] = byte(s >> 8)
	}
	return buf
}

func (g *Game) resetBall(dir float64) {
	g.ball.x = screenWidth/2 - ballSize/2
	g.ball.y = screenHeight/2 - ballSize/2
	g.speed = ballSpeed
	maxVY := ballSpeed * 0.7
	g.ballVY = (rand.Float64()*2 - 1) * maxVY
	g.ballVX = math.Sqrt(ballSpeed*ballSpeed-g.ballVY*g.ballVY) * dir
}

func (g *Game) Update() error {
	dt := 1.0 / float64(ebiten.TPS())

	if inpututil.IsKeyJustPressed(ebiten.KeySpace) {
		g.paused = !g.paused
	}
	if inpututil.IsKeyJustPressed(ebiten.KeyR) {
		g.leftScore, g.rightScore = 0, 0
		g.paused = false
		g.resetBall(1)
	}
	if inpututil.IsKeyJustPressed(ebiten.Key1) {
		g.vsAI = true
	}
	if inpututil.IsKeyJustPressed(ebiten.Key2) {
		g.vsAI = false
	}

	if g.paused {
		return nil
	}

	if ebiten.IsKeyPressed(ebiten.KeyW) {
		g.leftPaddle.y -= paddleSpeed * dt
	}
	if ebiten.IsKeyPressed(ebiten.KeyS) {
		g.leftPaddle.y += paddleSpeed * dt
	}
	if !g.vsAI {
		if ebiten.IsKeyPressed(ebiten.KeyUp) {
			g.rightPaddle.y -= paddleSpeed * dt
		}
		if ebiten.IsKeyPressed(ebiten.KeyDown) {
			g.rightPaddle.y += paddleSpeed * dt
		}
	} else {
		g.updateAI(dt)
	}

	if g.leftPaddle.y < 0 {
		g.leftPaddle.y = 0
	}
	if g.leftPaddle.y+paddleH > screenHeight {
		g.leftPaddle.y = screenHeight - paddleH
	}
	if g.rightPaddle.y < 0 {
		g.rightPaddle.y = 0
	}
	if g.rightPaddle.y+paddleH > screenHeight {
		g.rightPaddle.y = screenHeight - paddleH
	}

	g.ball.x += g.ballVX * dt
	g.ball.y += g.ballVY * dt

	if g.ball.y <= 0 {
		g.ball.y = 0
		g.ballVY = -g.ballVY
		g.play(g.sWall)
	}
	if g.ball.y+g.ball.h >= screenHeight {
		g.ball.y = screenHeight - g.ball.h
		g.ballVY = -g.ballVY
		g.play(g.sWall)
	}

	if g.ballVX < 0 && g.ball.overlaps(&g.leftPaddle) {
		g.ball.x = g.leftPaddle.x + g.leftPaddle.w
		g.bounceOffPaddle(&g.leftPaddle, 1)
		g.play(g.sPaddle)
	}
	if g.ballVX > 0 && g.ball.overlaps(&g.rightPaddle) {
		g.ball.x = g.rightPaddle.x - g.ball.w
		g.bounceOffPaddle(&g.rightPaddle, -1)
		g.play(g.sPaddle)
	}

	if g.ball.x+g.ball.w < 0 {
		g.rightScore++
		g.play(g.sScore)
		g.resetBall(1)
	}
	if g.ball.x > screenWidth {
		g.leftScore++
		g.play(g.sScore)
		g.resetBall(-1)
	}

	return nil
}

func (g *Game) updateAI(dt float64) {
	if g.ballVX < 0 {
		return
	}
	target := g.ball.y + g.ball.h/2 - paddleH/2
	diff := target - g.rightPaddle.y
	step := aiSpeed * dt
	if math.Abs(diff) <= step {
		g.rightPaddle.y = target
		return
	}
	g.rightPaddle.y += math.Copysign(step, diff)
}

func (g *Game) bounceOffPaddle(paddle *colorRect, dir float64) {
	rel := (g.ball.y + g.ball.h/2) - (paddle.y + paddle.h/2)
	rel /= paddle.h / 2
	if rel > 1 {
		rel = 1
	}
	if rel < -1 {
		rel = -1
	}
	g.speed = math.Min(g.speed*ballSpeedUp, maxBallSpeed)
	angle := rel * maxBounceAng
	g.ballVX = math.Cos(angle) * g.speed * dir
	g.ballVY = math.Sin(angle) * g.speed
}

func (g *Game) Draw(screen *ebiten.Image) {
	screen.Fill(color.RGBA{0x10, 0x10, 0x18, 0xff})

	for y := 0; y < screenHeight; y += 20 {
		ebitenutil.DrawRect(screen, screenWidth/2-2, float64(y), 4, 12, color.RGBA{0x60, 0x60, 0x70, 0xff})
	}

	g.leftPaddle.Draw(screen)
	g.rightPaddle.Draw(screen)
	g.ball.Draw(screen)

	ebitenutil.DebugPrintAt(screen, strconv.Itoa(g.leftScore), screenWidth/2-60, 20)
	ebitenutil.DebugPrintAt(screen, strconv.Itoa(g.rightScore), screenWidth/2+40, 20)
	ebitenutil.DebugPrintAt(screen, "W/S", 24, screenHeight-24)
	if g.vsAI {
		ebitenutil.DebugPrintAt(screen, "AI (1)", screenWidth-64, screenHeight-24)
	} else {
		ebitenutil.DebugPrintAt(screen, "UP/DOWN (2)", screenWidth-96, screenHeight-24)
	}

	if g.paused {
		ebitenutil.DebugPrintAt(screen, "PAUSED - SPACE to resume", screenWidth/2-100, screenHeight/2-8)
	}
}

func (g *Game) Layout(outsideWidth, outsideHeight int) (int, int) {
	return screenWidth, screenHeight
}

func main() {
	audioCtx = audio.NewContext(sampleRate)
	ebiten.SetWindowSize(screenWidth, screenHeight)
	ebiten.SetWindowTitle("Pong")
	if err := ebiten.RunGame(NewGame()); err != nil {
		log.Fatal(err)
	}
}
