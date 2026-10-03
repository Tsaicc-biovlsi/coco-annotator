<template>
  <div v-show="brush.isActive">
    <PanelInputNumber
      name="Radius"
      min="0"
      max="1000"
      step="5"
      v-model:value="brush.brush.pathOptions.radius"
    />
    <PanelInputString
      name="Stroke Color"
      v-model:value="brush.brush.pathOptions.strokeColor"
    />
  </div>
</template>

<script>
import PanelInputString from "@/components/PanelInputString.vue";
import PanelInputNumber from "@/components/PanelInputNumber.vue";

export default {
  name: "BrushPanel",
  components: { PanelInputString, PanelInputNumber },
  props: {
    brush: {
      type: Object,
      required: true
    }
  }
};
</script>
