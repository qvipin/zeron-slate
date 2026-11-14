-- Slate: a quiet neutral dark, layered grays and one restrained blue accent.
-- Ported from the Paseo "Slate" plugin. Data only (ds/palettes' shape).

return {
	name = "Slate",
	dark = {
		background = "#050608",
		raised = "#111418",
		text = "#e2e7f0",
		muted = "#8b95a8",
		faint = "#667086",
		accent = "#8aabe0",
		danger = "#e07a7a",
		warning = "#d6b06b",
		success = "#86c29a",
		-- comment, keyword, string, number, type, function, property,
		-- variable, punctuation, tag, attribute, invalid
		syntax = {
			"#667086", "#8aabe0", "#a9c6a0", "#d6a878", "#86c3c7", "#b8c9ea",
			"#c5cede", "#e2e7f0", "#8b95a8", "#8aabe0", "#d6b06b", "#e07a7a",
		},
		shell = "#08090b",
		card = "#0a0c0f",
		terminal = "#050608",
		-- black, red, green, yellow, blue, magenta, cyan, white, then bright
		ansi = {
			"#14171c", "#e07a7a", "#86c29a", "#d6b06b", "#8aabe0", "#b79ad6", "#86c3c7", "#c5cede",
			"#5d677b", "#ee9a9a", "#a3d6b3", "#e6c98f", "#a9c3ee", "#cdb5e6", "#a5dadd", "#f2f5fa",
		},
	},
}
