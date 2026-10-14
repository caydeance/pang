{
  description = "Pong - pygame development environment";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (ps: [ ps.pygame ]);
        in
        {
          default = pkgs.mkShell {
            packages = [ python ];
            shellHook = ''
              export SDL_VIDEODRIVER=wayland,x11
            '';
          };
        }
      );
    };
}
