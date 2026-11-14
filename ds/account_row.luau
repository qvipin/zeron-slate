-- You and settings, at a sidebar's foot (the settings window's, where the
-- main sidebar's own foot isn't): your avatar and name, your profile, shown
-- chosen while it's open; and beside you settings' own button, a toggle on
-- while they're open, a click again closing them.
--
-- Slate: drawn as Slate's main sidebar foot draws you, so nothing moves
-- between the two: a bar of its own (a hairline over it) across the list's
-- whole width, down to the window's foot, FOOT tall; your avatar's edge 12
-- in, your name 36 in with a line under it; the gear the "…"'s size, 8 in
-- from the right, on the bar's middle.
--
--   AccountRow { name = fn, id = fn, avatar = fn, on_user = fn, user_open = fn,
--                on_settings = fn, settings_open = fn }

local Surface = require("@self/surface")
local Avatar = require("@self/avatar")
local ToggleButton = require("@self/toggle_button")
local FadeText = require("@self/fade_text")
local locale = require("@self/locale")

export type Props = {
	name: () -> string,
	id: (() -> string?)?,
	avatar: (() -> string?)?,
	on_user: () -> (),
	user_open: () -> boolean,
	on_settings: () -> (),
	settings_open: () -> boolean,
}

-- The bar's height (Slate's sidebar FOOT), and where things stand in it.
local FOOT = 46
local TOP = 12
local AVATAR = 20
local WORDS = 36
local GEAR = 24
local EDGE = 8

return function(props: Props): Node
	local on = ui.use_state(props.settings_open())
	ui.effect(function()
		local v = props.settings_open()
		if on:peek() ~= v then
			on:set(v)
		end
	end)
	return ui.column {
		w_full = true,
		shrink = 0,
		ui.div { w_full = true, h = 1, shrink = 0, bg = "$border.subtle" },
		ui.div {
			w_full = true,
			h = FOOT,
			shrink = 0,
			relative = true,
			Surface {
				depth = "flat",
				selected = props.user_open,
				on_click = props.on_user,
				label = props.name,
				w_full = true,
				h = FOOT,
				border = 0,
				rounded = 0,
				items = "center",
				direction = "row",
				pl = TOP,
				pr = EDGE + GEAR + EDGE,
				gap = WORDS - TOP - AVATAR,
				ui.div {
					w = AVATAR,
					h = AVATAR,
					shrink = 0,
					ui.presence(function(): string
						return (if props.id then props.id() else nil) or props.name()
					end, function(seed: string): Node
						return Avatar {
							seed = seed,
							size = AVATAR,
							label = props.name(),
							src = function(): string?
								return if props.avatar then props.avatar() else nil
							end,
						}
					end),
				},
				ui.column {
					grow = 1,
					min_w = 0,
					gap = 1,
					FadeText {
						props.name,
						min_w = 0,
						text_size = "$font.size.sm",
						weight = "$font.weight.medium",
						color = "$text.primary",
					},
					ui.text { "Your profile", text_size = "$font.size.xs", color = "$text.tertiary" },
				},
			},
			ui.div {
				absolute = true,
				right = EDGE,
				top = (FOOT - GEAR) / 2,
				ToggleButton {
					on = on,
					-- (ToggleButton's label is its tooltip: a string.)
					label = locale.s("ds.account_row.settings"),
					icon = "settings",
					tone = "quiet",
					w = GEAR,
					h = GEAR,
					rounded = "$radius.sm",
					shrink = 0,
					on_change = function()
						props.on_settings()
					end,
				},
			},
		},
	}
end
