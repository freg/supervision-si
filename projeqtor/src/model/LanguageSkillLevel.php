<?php

/* ============================================================================
 * Language skill level
 */
require_once('_securityCheck.php');
class LanguageSkillLevel extends SqlElement {

    // extends SqlElement, so has $id
    public $_sec_Description;
    public $id;    // redefine $id to specify its visible place
    public $name;
    public $color;
    public $sortOrder=0;
    public $idle;

    private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%"># ${id}</th>
    <th field="name" width="60%">${name}</th>
    <th field="color" width="15%" formatter="colorFormatter">${color}</th>
    <th field="sortOrder"  formatter="numericFormatter" width="10%">${sortOrderShort}</th>  
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';
    /** ==========================================================================
     * Constructor
     * @param $id Int the id of the object in the database (null if not stored yet)
     * @return void
     */
    function __construct($id = NULL, $withoutDependentObjects=false) {
        parent::__construct($id,$withoutDependentObjects);
    }


    /** ==========================================================================
     * Destructor
     * @return void
     */
    function __destruct() {
        parent::__destruct();
    }

// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********

    /** ==========================================================================
     * Return the specific layout
     * @return String the layout
     */
    protected function getStaticLayout() {
        return self::$_layout;
    }


}
?>