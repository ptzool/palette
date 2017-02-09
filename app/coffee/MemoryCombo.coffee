define 'MemoryCombo', [
    'ComboButton'
], (ComboButton) ->
    class MemoryCombo extends ComboButton
        constructor: (props) ->
            super props
            @options = [null, 500, 600, 700, 800, 900,
                        1024, 1024 + 512, 2048, 2048 + 512, 3 * 1024,
                        3 * 1024 + 512, 4 * 1024]

        valueWithMetric: (value) =>
            metric = @metric value
            if not @optionEnabled value
                "Do Not Monitor"
            else
                if value >= 1024
                    value = value / 1024
                value + metric


        metric: (value) ->
            if value >= 1024
                " GB"
            else
                " MB"

        optionEnabled: (value) ->
            value?


