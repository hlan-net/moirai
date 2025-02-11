<template>
  <div class="main">
    <h1>{{ msg }}</h1>
    <h3>To Be Added</h3>
    <ul>
      <li>Status</li>
      <li>Feeds</li>
      <li>Events</li>
    </ul>
  </div>
</template>

<script>
export default {
  name: 'MainPage',
  props: {
    msg: String
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
h3 {
  margin: 40px 0 0;
}
ul {
  list-style-type: none;
  padding: 0;
}
li {
  display: inline-block;
  margin: 0 10px;
}
a {
  color: #42b983;
}
</style>
