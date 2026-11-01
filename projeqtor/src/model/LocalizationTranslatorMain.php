<?php



/** ============================================================================
 * Resource specialized in translation
 */
require_once('_securityCheck.php');
class LocalizationTranslatorMain extends SqlElement {

    public $_sec_description;
    public $id;    // redefine $id to specify its visible place
    public $name;
    public $idResource;
    public $idle;
    public $_sec_languageSkill;
    public $_languageSkill;

    private static $_layout='
    <th field="id" formatter="numericFormatter" width="15%"># ${id}</th>
    <th field="name" width="75%">${name}</th>
    <th field="idle" width="10%" formatter="booleanFormatter">${idle}</th>
    ';



    private static $_fieldsAttributes=array(
        "id"=>"",
        "name"=>"hidden",
        "idResource"=>"required",
        "idle"=>"nobr"
    );

    private static $_colCaptionTransposition = array(
        'idResource'=> 'resource',
    );

    private static $_databaseTableName = 'localizationtranslator';
    private static $_databaseCriteria = array();
    private static $_databaseColumnName = array();

    /**
     * LocalizationTranslatorMain constructor.
     * @param $_sec_description
     */
    public function __construct($id = NULL, $withoutDependentObjects=false)
    {
        parent::__construct($id,$withoutDependentObjects);
        if ($withoutDependentObjects) return;


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

    /** ========================================================================
     * Return the specific databaseTableName
     * @return String the databaseTableName
     */
    protected function getStaticDatabaseTableName() {
        $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
        return $paramDbPrefix . self::$_databaseTableName;
    }

    /** ========================================================================
     * Return the specific database criteria
     * @return String the databaseTableName
     */
    protected function getStaticDatabaseCriteria() {
        return self::$_databaseCriteria;
    }

    /** ==========================================================================
     * Return the specific fieldsAttributes
     * @return Array the fieldsAttributes  
     */
    protected function getStaticFieldsAttributes() {
        return self::$_fieldsAttributes;
    }

    /** ============================================================================
     * Return the specific colCaptionTransposition
     * @return String the colCaptionTransposition
     */
    protected function getStaticColCaptionTransposition($fld=null) {
        return self::$_colCaptionTransposition;
    }

    /** ========================================================================
     * Return the specific databaseColumnName
     * @return String the databaseTableName
     */
    protected function getStaticDatabaseColumnName() {
        return self::$_databaseColumnName;
    }


    public function save() {
        $old=$this->getOld();

        if ($old->idResource != $this->idResource){
            // update column name wich is hidden if idResource change --> affect name of ressource
            $resource = new ResourceAll($this->idResource);
            $this->name = $resource->name;
        }

        $result = parent::save();
        return $result;
    }
}