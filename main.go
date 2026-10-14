package main

import (
	"image/color"
	"log"
	"strconv"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/ebitenutil"
	"github.com/hajimehoshi/ebiten/v2/inpututil"
)

const (
	screenWidth  = 640
	screenHeight = 480

	paddleW = 12
	paddleH = 80
	paddleX = 24

	paddleSpeed = 6
	ballSize    = 12
	ballSpeed   = 5
)

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

	leftScore  int
	rightScore int
}

func NewGame() *Game {
	g := &Game{
		leftPaddle:  colorRect{x: paddleX, y: screenHeight/2 - paddleH/2, w: paddleW, h: paddleH, clr: white},
		rightPaddle: colorRect{x: screenWidth - paddleX - paddleW, y: screenHeight/2 - paddleH/2, w: paddleW, h: paddleH, clr: white},
		ball:        colorRect{x: screenWidth/2 - ballSize/2, y: screenHeight/2 - ballSize/2, w: ballSize, h: ballSize, clr: white},
	}
	g.resetBall(1)
	return g
}

func (g *Game) resetBall(dir float64) {
	g.ball.x = screenWidth/2 - ballSize/2
	g.ball.y = screenHeight/2 - ballSize/2
	g.ballVX = ballSpeed * dir
	g.ballVY = ballSpeed * 0.75
}

func (g *Game) Update() error {
	if ebiten.IsKeyPressed(ebiten.KeyW) {
		g.leftPaddle.y -= paddleSpeed
	}
	if ebiten.IsKeyPressed(ebiten.KeyS) {
		g.leftPaddle.y += paddleSpeed
	}
	if ebiten.IsKeyPressed(ebiten.KeyUp) {
		g.rightPaddle.y -= paddleSpeed
	}
	if ebiten.IsKeyPressed(ebiten.KeyDown) {
		g.rightPaddle.y += paddleSpeed
	}
	if inpututil.IsKeyJustPressed(ebiten.KeyR) {
		g.leftScore, g.rightScore = 0, 0
		g.resetBall(1)
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

	g.ball.x += g.ballVX
	g.ball.y += g.ballVY

	if g.ball.y <= 0 {
		g.ball.y = 0
		g.ballVY = -g.ballVY
	}
	if g.ball.y+g.ball.h >= screenHeight {
		g.ball.y = screenHeight - g.ball.h
		g.ballVY = -g.ballVY
	}

	if g.ballVX < 0 && g.ball.overlaps(&g.leftPaddle) {
		g.ball.x = g.leftPaddle.x + g.leftPaddle.w
		g.bounceOffPaddle(&g.leftPaddle, 1)
	}
	if g.ballVX > 0 && g.ball.overlaps(&g.rightPaddle) {
		g.ball.x = g.rightPaddle.x - g.ball.w
		g.bounceOffPaddle(&g.rightPaddle, -1)
	}

	if g.ball.x+g.ball.w < 0 {
		g.rightScore++
		g.resetBall(1)
	}
	if g.ball.x > screenWidth {
		g.leftScore++
		g.resetBall(-1)
	}

	return nil
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
	speed := ballSpeed * 1.2
	g.ballVX = speed * dir
	g.ballVY = speed * rel
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
	ebitenutil.DebugPrintAt(screen, "UP/DOWN", screenWidth-90, screenHeight-24)
}

func (g *Game) Layout(outsideWidth, outsideHeight int) (int, int) {
	return screenWidth, screenHeight
}

func main() {
	ebiten.SetWindowSize(screenWidth, screenHeight)
	ebiten.SetWindowTitle("Pong")
	if err := ebiten.RunGame(NewGame()); err != nil {
		log.Fatal(err)
	}
}
