<?php


class LocalizationRequestType extends Type
{
    // extends SqlElement, so has $id
    public $_sec_Description;
    public $id;    // redefine $id to specify its visible place
    public $name;
    public $code;
    public $idWorkflow;
    public $priority;
    public $sortOrder=0;
    public $idle;
    public $description;
    public $_sec_Behavior;
    public $idStatus;
    public $numberDaysBeforeDueDate;
    public $mandatoryDescription;
    public $_lib_mandatoryField;
    public $mandatoryResourceOnHandled;
    public $_lib_mandatoryOnHandledStatus;
    public $lockDone;
    public $_lib_statusMustChangeDone;
    public $lockIdle;
    public $_lib_statusMustChangeIdle;
    public $lockCancelled;
    public $_lib_statusMustChangeCancelled;
    

    private static $_databaseCriteria = array('scope'=>'LocalizationRequest');

    private static $_fieldsAttributes=array("name"=>"required",
        "idWorkflow"=>"required",
        "mandatoryDescription"=>"nobr",
        "mandatoryResourceOnHandled"=>"nobr",
        "mandatoryResultOnDone"=>"hidden",
        "_lib_mandatoryOnDoneStatus"=>"hidden",
        "mandatoryResolutionOnDone"=>"hidden",
        "_lib_mandatoryResolutionOnDoneStatus"=>"hidden",
        "lockHandled"=>"hidden",
        "_lib_statusMustChangeHandled"=>"hidden",
        "lockDone"=>"nobr",
        "lockSolved"=>"hidden",
        "lockIdle"=>"nobr",
        "lockCancelled"=>"nobr",
        "internalData"=>"hidden",
        "showInFlash"=>"hidden",
        "scope"=>"hidden",
        "lockNoLeftOnDone"=>"hidden",
        "_lib_statusMustChangeLeftDone"=>"hidden",
        "color"=>"hidden",
        "priority"=>"hidden"
    );

    private static $_colCaptionTransposition = array(
        'idStatus'=> 'statusCreationLocalizationItem'
    );

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
    return array_merge(parent::getStaticFieldsAttributes(),self::$_fieldsAttributes);
    //return self::$_fieldsAttributes;
  }

    /** ============================================================================
     * Return the specific colCaptionTransposition
     * @return String the colCaptionTransposition
     */
    protected function getStaticColCaptionTransposition($fld=null) {
        return self::$_colCaptionTransposition;
    }

}